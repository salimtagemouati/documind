"""Verify a built API image starts as non-root and serves readiness, then remove it."""
import http.client
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else 'documind-audit:local'
    name = 'documind-runtime-' + secrets.token_hex(4)
    subprocess.run(['docker', 'run', '--rm', '-d', '--name', name,
        '-p', '127.0.0.1::8080', '-e', 'SECRET_KEY=' + secrets.token_hex(32),
        '-e', 'SUPABASE_URL=https://unused.invalid', '-e', 'SUPABASE_ANON_KEY=',
        '-e', 'SUPABASE_SERVICE_KEY=', '-e', 'DATABASE_URL=sqlite+aiosqlite:////app/data/smoke.db',
        '-e', 'REDIS_URL=', '-e', 'LITELLM_LOCAL_MODEL_COST_MAP=True', image],
        check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(['docker', 'port', name, '8080'], text=True).strip().rsplit(':', 1)[1]
        uid = subprocess.check_output(['docker', 'exec', name, 'id', '-u'], text=True).strip()
        assert uid != '0', 'API container must not run as root'
        for _ in range(100):
            try:
                with urllib.request.urlopen('http://127.0.0.1:' + port + '/ready', timeout=2) as response:
                    result = json.load(response)
                    assert result['status'] == 'healthy'
                    print('PASS: built non-root container starts and serves healthy readiness')
                    return
            except (urllib.error.URLError, http.client.HTTPException, OSError, TimeoutError):
                time.sleep(.5)
        raise RuntimeError('Container readiness did not pass')
    finally:
        subprocess.run(['docker', 'stop', name], stdout=subprocess.DEVNULL, check=False)


if __name__ == '__main__':
    main()
