"""Run a real API process against disposable SQLite, without external credentials.

Usage: backend/.venv/bin/python scripts/smoke_test.py
"""
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def main() -> None:
    backend = Path(__file__).resolve().parents[1] / 'backend'
    with tempfile.TemporaryDirectory(prefix='documind-smoke-') as directory:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'PYTHONPATH': str(backend),
               'SECRET_KEY': secrets.token_hex(32), 'ENVIRONMENT': 'test',
               'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
               'DATABASE_URL': f'sqlite+aiosqlite:///{directory}/smoke.db',
               'LOCAL_UPLOAD_DIR': f'{directory}/uploads', 'REDIS_URL': '',
               'SUPABASE_URL': 'https://unused.invalid', 'SUPABASE_ANON_KEY': '',
               'SUPABASE_SERVICE_KEY': '', 'GOOGLE_API_KEY': '', 'GEMINI_API_KEY': '',
               'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'GROQ_API_KEY': '',
               'STRIPE_SECRET_KEY': '', 'STRIPE_WEBHOOK_SECRET': '', 'SENTRY_DSN': ''}
        # Start outside the checkout: the developer's .env must never affect this test.
        with (Path(directory) / "server.log").open("w") as log_file:
            process = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
                 '--port', str(port), '--no-access-log'], cwd=directory, env=env,
                stdout=log_file, stderr=subprocess.STDOUT,
            )
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10) as client:
                deadline = time.monotonic() + 300
                while True:
                    if process.poll() is not None:
                        raise RuntimeError('API exited before becoming ready')
                    try:
                        if client.get('/ready').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError('API did not become ready within 300 seconds: ' + (Path(directory) / 'server.log').read_text()[-4000:])
                    time.sleep(0.25)
                response = client.post('/api/v1/auth/demo')
                response.raise_for_status()
                token = response.json()['access_token']
                client.headers['Authorization'] = f'Bearer {token}'
                docs_response = client.get('/api/v1/documents/')
                docs_response.raise_for_status()
                docs = docs_response.json()['items']
                assert len(docs) == 3, 'Demo must contain three sample documents'
                for doc in docs:
                    analysis = client.get(f"/api/v1/documents/{doc['id']}/analysis")
                    analysis.raise_for_status()
                    assert analysis.json()['summary']
                blocked = client.delete(f"/api/v1/documents/{docs[0]['id']}")
                assert blocked.status_code == 403, 'Demo must be read-only'
                auth = client.post('/api/v1/auth/register', json={
                    'email': 'smoke@example.com', 'password': secrets.token_hex(16) + 'Aa1!'
                })
                auth.raise_for_status()
                client.headers['Authorization'] = f"Bearer {auth.json()['access_token']}"
                own_docs = client.get('/api/v1/documents/')
                own_docs.raise_for_status()
                assert own_docs.json()['items'] == [], 'Accounts must be isolated'
                assert client.get(f"/api/v1/documents/{docs[0]['id']}").status_code == 404
                empty = client.post('/api/v1/documents/upload', files={'file': ('empty.txt', b'', 'text/plain')})
                assert empty.status_code == 422
                malformed = client.post('/api/v1/documents/upload', files={'file': ('broken.pdf', b'not a PDF', 'application/pdf')})
                assert malformed.status_code == 202
                malformed_id = malformed.json()['id']
                for _ in range(40):
                    metadata = client.get('/api/v1/documents/' + malformed_id).json()
                    if metadata['status'] == 'failed':
                        break
                    time.sleep(.1)
                assert metadata['status'] == 'failed' and metadata['error_message']
                assert client.delete('/api/v1/documents/' + malformed_id).status_code == 200
                print('PASS: real API startup, readiness, demo, analyses, write protection, registration, tenant isolation, empty-file validation, malformed-PDF failure and deletion')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
