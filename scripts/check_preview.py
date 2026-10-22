"""Exercise the running public preview with synthetic data and real Gemini.

Reads the URL from the private launcher state. Creates two synthetic accounts,
deletes the test document and retains a secret-free evidence report.
"""
import json
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode

import httpx
from websockets.sync.client import connect

from live_gemini_smoke import pdf_fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    base = json.loads((ROOT / 'backend/data/preview/state.json').read_text())['public_url']
    report = {'url': base, 'checks': [], 'fixtures': 'synthetic only'}
    with httpx.Client(base_url=base, timeout=100) as client:
        for route in ['/', '/register', '/ready']:
            assert client.get(route).status_code == 200, route
        for route in ['/api/missing', '/.env', '/assets/missing.js']:
            assert client.get(route).status_code == 404, route
        report['checks'].append('Public HTTPS, SPA deep routes, readiness and private/missing paths')

        def signup():
            response = client.post('/api/v1/auth/register', json={
                'email': f'preview-{secrets.token_hex(5)}@example.com',
                'password': secrets.token_hex(16) + 'Aa1!',
            })
            assert response.status_code == 201, f'register HTTP {response.status_code}'
            return response.json()['access_token']

        owner, outsider = signup(), signup()
        headers = {'Authorization': 'Bearer ' + owner}
        uploaded = client.post('/api/v1/documents/upload', headers=headers,
                               files={'file': ('launch-contract.pdf', pdf_fixture(), 'application/pdf')})
        assert uploaded.status_code == 202, f'upload HTTP {uploaded.status_code}'
        document_id = uploaded.json()['id']
        try:
            start = time.monotonic()
            while time.monotonic() - start < 150:
                meta = client.get('/api/v1/documents/' + document_id, headers=headers).json()
                if meta['status'] in ['ready', 'failed']:
                    break
                time.sleep(3)
            assert meta['status'] == 'ready', meta.get('error_message')
            report['checks'].append('Public PDF upload, Gemini analysis and persistent pgvector indexing')
            assert client.get('/api/v1/documents/' + document_id,
                              headers={'Authorization': 'Bearer ' + outsider}).status_code == 404
            report['checks'].append('Separate account cannot read another account document')
            ws_url = base.replace('https://', 'wss://') + '/api/v1/ws/documents/' + document_id
            with connect(ws_url + '?' + urlencode({'token': owner}), open_timeout=20) as websocket:
                assert json.loads(websocket.recv(timeout=20))['stage'] == 'complete'
            report['checks'].append('Authenticated public WSS progress connection')
            answered = client.post('/api/v1/query/', headers=headers,
                                   json={'document_id': document_id, 'question': 'How long does the warranty last?'})
            assert answered.status_code == 200, f'query HTTP {answered.status_code}'
            data = answered.json()
            assert '24' in data['answer']
            assert any(source['page_number'] == 2 for source in data['sources'])
            report['answer'] = data['answer']
            report['checks'].append('Public live answer with page 2 citation')
        finally:
            assert client.delete('/api/v1/documents/' + document_id, headers=headers).status_code == 200
        assert client.get('/api/v1/documents/' + document_id, headers=headers).status_code == 404
        report['checks'].append('Public document deletion')
    report['status'] = 'passed'
    target = ROOT / 'docs/verification/public-preview.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
