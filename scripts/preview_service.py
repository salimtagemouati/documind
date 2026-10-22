"""Manage the DocuMind preview as a per-user macOS login service."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'com.documind.preview'
PLIST = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
DOMAIN = f'gui/{os.getuid()}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'remove', 'status'])
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('This helper requires macOS; use preview.py elsewhere.')
    if args.command == 'status':
        result = subprocess.run(['launchctl', 'print', f'{DOMAIN}/{LABEL}'], capture_output=True, text=True)
        print('Login service loaded' if result.returncode == 0 else 'Login service not loaded')
        subprocess.run([sys.executable, str(ROOT / 'scripts/preview.py'), 'status'], check=True)
        return
    if PLIST.exists():
        prior = plistlib.loads(PLIST.read_bytes())
        if prior.get('ProgramArguments', [None, None])[1] != str(ROOT / 'scripts/preview.py'):
            raise SystemExit('Existing service belongs to a different checkout; refusing to replace it.')
        subprocess.run(['launchctl', 'bootout', DOMAIN, str(PLIST)], capture_output=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/preview.py'), 'stop'], check=True)
    if args.command == 'remove':
        PLIST.unlink(missing_ok=True)
        print('Login service removed. Preview data is preserved.')
        return
    data = ROOT / 'backend/data/preview'
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    config = {
        'Label': LABEL,
        'ProgramArguments': [sys.executable, str(ROOT / 'scripts/preview.py'), 'serve', '--share'],
        'WorkingDirectory': str(ROOT),
        'EnvironmentVariables': {'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')},
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30,
        'StandardOutPath': str(data / 'service.log'),
        'StandardErrorPath': str(data / 'service.log'),
        'Umask': 63,
    }
    with PLIST.open('wb') as handle:
        PLIST.chmod(0o600)
        plistlib.dump(config, handle)
    subprocess.run(['launchctl', 'bootstrap', DOMAIN, str(PLIST)], check=True)
    print('DocuMind login service installed. It restarts after exit and at login.')
    print('Run preview.py status for the URL after startup completes.')


if __name__ == '__main__':
    main()
