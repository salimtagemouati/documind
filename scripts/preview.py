"""Start/stop a persistent, isolated DocuMind preview without cloud accounts.

Uses the existing backend virtualenv, Docker and Node. --share additionally needs
cloudflared. All data and private runtime settings stay in backend/data/preview.
The public URL is temporary and requires this Mac to stay awake and connected.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/preview"
STATE = DATA / "state.json"
PRIVATE = DATA / "private.json"
DB_NAME = "documind-preview-db"
LABEL = "com.documind.preview"
PORT = 8765


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        temporary.chmod(0o600)
        json.dump(value, handle, indent=2)
    temporary.replace(path)


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def is_running(pid):
    if not isinstance(pid, int):
        return False
    command = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True).stdout
    return str(Path(__file__).resolve()) in command and "serve" in command


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, **kwargs).strip()


def database(config):
    inspected = subprocess.run(["docker", "inspect", DB_NAME], capture_output=True, text=True)
    if inspected.returncode == 0:
        existing = json.loads(inspected.stdout)[0]
        if existing["Config"].get("Labels", {}).get(LABEL) != str(ROOT):
            raise RuntimeError("A container with the preview name belongs to another application")
        run("docker", "start", DB_NAME)
    else:
        env_file = DATA / "postgres.env"
        with env_file.open("w") as handle:
            env_file.chmod(0o600)
            handle.write("POSTGRES_PASSWORD=" + config["database_password"] + "\n")
        run("docker", "run", "-d", "--name", DB_NAME, "--label", f"{LABEL}={ROOT}",
            "--env-file", str(env_file), "-p", "127.0.0.1::5432", "-v",
            f"{DATA / 'postgres'}:/var/lib/postgresql/data", "pgvector/pgvector:pg16")
    for _ in range(60):
        check = subprocess.run(["docker", "exec", DB_NAME, "pg_isready", "-U", "postgres"], capture_output=True)
        if check.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Preview database did not become ready")
    port = run("docker", "port", DB_NAME, "5432").rsplit(":", 1)[1]
    return f"postgresql+asyncpg://postgres:{config['database_password']}@127.0.0.1:{port}/postgres"


async def initialize_database():
    from sqlalchemy import text
    from app.db.database import engine
    from app.models.models import Base
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for statement in (ROOT / "backend/migrations/003_pgvector.sql").read_text().split(";"):
            if statement.strip():
                await conn.execute(text(statement))
    await engine.dispose()


def serve(share):
    os.umask(0o077)
    children = []
    handles = []
    runtime = {"pid": os.getpid(), "status": "starting", "local_url": f"http://127.0.0.1:{PORT}"}
    save(STATE, runtime)

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        # Never mistake an unrelated service on this port for our own API.
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", PORT))
        config = json.loads(PRIVATE.read_text()) if PRIVATE.exists() else {
            "database_password": secrets.token_hex(32), "signing_secret": secrets.token_hex(32),
        }
        save(PRIVATE, config)
        values = dotenv_values(ROOT / "backend/.env")
        if not values.get("GOOGLE_API_KEY"):
            raise RuntimeError("The existing backend/.env needs GOOGLE_API_KEY")
        url = database(config)
        env = {**os.environ, **{k: v for k, v in values.items() if v is not None},
               "DATABASE_URL": url, "SECRET_KEY": config["signing_secret"],
               "ENVIRONMENT": "production", "DEBUG": "false", "STORAGE_BACKEND": "local",
               "LOCAL_UPLOAD_DIR": str(DATA / "uploads"), "REDIS_URL": "",
               "FRONTEND_DIST_DIR": str(ROOT / "frontend/dist"), "ANALYSIS_MODE": "combined",
               "STRIPE_SECRET_KEY": "", "SENTRY_DSN": "", "LITELLM_LOCAL_MODEL_COST_MAP": "True",
               "SUPABASE_URL": "https://unused.invalid", "SUPABASE_ANON_KEY": "", "SUPABASE_SERVICE_KEY": "",
               "PYTHONPATH": str(ROOT / "backend"), "FRONTEND_URL": runtime["local_url"],
               "ALLOWED_ORIGINS": json.dumps([runtime["local_url"]])}
        os.environ.update(env)
        sys.path.insert(0, str(ROOT / "backend"))
        asyncio.run(initialize_database())
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend",
                       env={**os.environ, "VITE_API_URL": "/api/v1"}, check=True)
        api_log = (DATA / "api.log").open("a")
        handles.append(api_log)
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                "--port", str(PORT), "--no-access-log", "--no-proxy-headers", "--log-level", "warning"],
                               cwd=ROOT / "backend", env=env, stdout=api_log, stderr=subprocess.STDOUT)
        children.append(api)
        for _ in range(90):
            if api.poll() is not None:
                raise RuntimeError("Preview API exited; inspect backend/data/preview/api.log locally")
            try:
                if httpx.get(runtime["local_url"] + "/ready", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Preview API readiness timed out")
        runtime["status"] = "running"
        if share:
            tunnel_log = DATA / "tunnel.log"
            tunnel_handle = tunnel_log.open("w")
            handles.append(tunnel_handle)
            tunnel = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", runtime["local_url"]],
                                      stdout=tunnel_handle, stderr=subprocess.STDOUT)
            children.append(tunnel)
            for _ in range(60):
                urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", tunnel_log.read_text())
                if urls:
                    runtime["public_url"] = urls[-1]
                    break
                if tunnel.poll() is not None:
                    break
                time.sleep(1)
        save(STATE, runtime)
        while api.poll() is None:
            if share and tunnel.poll() is not None:
                runtime.pop("public_url", None)
                runtime["tunnel_status"] = "stopped"
                save(STATE, runtime)
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Never log connection URLs, environment variables or provider credentials.
        runtime["error_type"] = type(exc).__name__
        if isinstance(exc, OSError):
            runtime["error_number"] = exc.errno
        print("Preview startup failed:", type(exc).__name__, flush=True)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        for handle in handles:
            handle.close()
        runtime["status"] = "stopped"
        runtime.pop("public_url", None)
        save(STATE, runtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "status", "serve"])
    parser.add_argument("--share", action="store_true", help="Create a temporary public HTTPS preview")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.command == "serve":
        return serve(args.share)
    current = state()
    running = is_running(current.get("pid"))
    if args.command == "stop":
        if running:
            os.kill(current["pid"], signal.SIGTERM)
            for _ in range(25):
                if not is_running(current["pid"]):
                    break
                time.sleep(1)
        print("Preview stopped; database and uploaded files are preserved.")
    elif args.command == "status" or running:
        if not running:
            current["status"] = "stopped"
            current.pop("public_url", None)
        print(json.dumps({**current, "process_running": running}, indent=2))
    else:
        for executable in ["docker", "npm"] + (["cloudflared"] if args.share else []):
            if not shutil.which(executable):
                raise SystemExit(f"Missing executable: {executable}")
        args_list = [sys.executable, str(Path(__file__).resolve()), "serve"]
        if args.share:
            args_list.append("--share")
        with (DATA / "launcher.log").open("a") as log:
            (DATA / "launcher.log").chmod(0o600)
            process = subprocess.Popen(args_list, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(180):
            current = state()
            if current.get("pid") == process.pid and current.get("status") != "starting":
                print(json.dumps(current, indent=2))
                return
            if process.poll() is not None:
                raise SystemExit("Preview failed to start; inspect backend/data/preview/launcher.log locally")
            time.sleep(1)
        raise SystemExit("Preview still starting; run the status command for progress")


if __name__ == "__main__":
    main()
