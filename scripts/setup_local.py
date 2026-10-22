"""Create local environment files without overwriting existing configuration."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for folder in ('backend', 'frontend'):
    target = root / folder / '.env'
    if target.exists():
        print(f'Kept existing {folder}/.env')
        continue
    template = target.with_name('.env.example').read_text()
    try:
        with target.open('x') as handle:
            target.chmod(0o600)
            handle.write(template.replace('SECRET_KEY=REPLACE_ME', f'SECRET_KEY={secrets.token_hex(32)}'))
        print(f'Created {folder}/.env')
    except FileExistsError:
        print(f'Kept existing {folder}/.env')
print('Local configuration ready. Add a provider key to backend/.env for AI generation.')
