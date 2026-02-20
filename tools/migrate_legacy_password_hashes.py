#!/usr/bin/env python3
import configparser
import hashlib
import re
from getpass import getpass
from pathlib import Path

from django.contrib.auth.hashers import make_password

CONFIG_FILE = Path.home() / '.screenly' / 'screenly.conf'
LEGACY_SHA256_RE = re.compile(r'^[a-f0-9]{64}$')


def main() -> int:
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if 'auth_basic' not in config or 'password' not in config['auth_basic']:
        print('No BasicAuth password found, nothing to migrate.')
        return 0

    password = config['auth_basic']['password'].strip()
    if not LEGACY_SHA256_RE.fullmatch(password):
        print('Password is already using a modern password hash format.')
        return 0

    print('Legacy SHA256 hash detected. Enter the plaintext password to migrate.')
    plaintext = getpass('Password: ')
    if hashlib.sha256(plaintext.encode('utf-8')).hexdigest() != password:
        print('Provided password does not match existing hash; aborting.')
        return 1

    config['auth_basic']['password'] = make_password(plaintext)
    with CONFIG_FILE.open('w') as f:
        config.write(f)

    print(f'Migrated legacy hash in {CONFIG_FILE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
