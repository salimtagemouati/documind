"""Prepare an ignored private production environment without touching hosted services."""
import secrets
from pathlib import Path

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    target = ROOT / 'backend/.env.production'
    template = ROOT/'backend/.env.production.example'
    if target.exists():
        print('Kept existing backend/.env.production')
    else:
        content = template.read_text()
        local = dotenv_values(ROOT/'backend/.env')
        with target.open('x') as handle:
            target.chmod(0o600)
            handle.write(content)
        set_key(str(target), 'SECRET_KEY', secrets.token_hex(32))
        if local.get('GOOGLE_API_KEY'):
            set_key(str(target), 'GOOGLE_API_KEY', local['GOOGLE_API_KEY'])
        print('Created private ignored backend/.env.production; fill the hosting and database placeholders locally.')
