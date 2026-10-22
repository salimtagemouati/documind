from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.spa import SPAStaticFiles


def test_spa_routes_preserve_api_and_asset_404s(tmp_path):
    (tmp_path / 'index.html').write_text('<html>DocuMind</html>')
    (tmp_path / '.env').write_text('test-only-hidden-file')
    app = FastAPI()
    app.mount('/', SPAStaticFiles(directory=tmp_path, html=True))
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert 'DocuMind' in client.get('/dashboard').text
        for path in ['/api/missing', '/assets/missing.js', '/missing.js', '/.env']:
            assert client.get(path).status_code == 404
        assert client.post('/dashboard').status_code == 405
