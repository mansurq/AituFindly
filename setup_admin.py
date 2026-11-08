from pathlib import Path
import json
from getpass import getpass
from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    target = Path(__file__).resolve().parent / 'instance' / 'admin.json'
    target.parent.mkdir(exist_ok=True)
    print('Create or reset the Findly administrator password.')
    while True:
        password = getpass('New password (at least 8 characters): ')
        if len(password) < 8:
            print('Use at least 8 characters.')
            continue
        if password != getpass('Repeat password: '):
            print('Passwords do not match.')
            continue
        target.write_text(json.dumps({'password_hash': generate_password_hash(password)}))
        # Reset all existing signed sessions when changing the administrator password.
        import secrets
        (target.parent / 'session.key').write_text(secrets.token_hex(32))
        print('Saved. Start or restart Findly, then open Administration.')
        break
