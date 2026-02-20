import hashlib
import hmac
import json
import logging
import os
import time
from collections import deque
from typing import Any

COMMAND_SIGNING_SECRET_ENV = 'HOSTCMD_SIGNING_SECRET'
COMMAND_MAX_AGE_SECONDS = int(os.getenv('HOSTCMD_MAX_AGE_SECONDS', '60'))
HOSTCMD_RATE_LIMIT_SECONDS = int(os.getenv('HOSTCMD_RATE_LIMIT_SECONDS', '300'))


def _get_secret() -> str:
    secret = os.getenv(COMMAND_SIGNING_SECRET_ENV, '')
    if not secret:
        raise ValueError(f'{COMMAND_SIGNING_SECRET_ENV} is required')
    return secret


def build_signed_hostcmd_payload(cmd: str) -> str:
    ts = int(time.time())
    nonce = os.urandom(16).hex()
    sig = sign_host_command(cmd=cmd, ts=ts, nonce=nonce)
    return json.dumps({'cmd': cmd, 'ts': ts, 'nonce': nonce, 'sig': sig})


def sign_host_command(cmd: str, ts: int, nonce: str) -> str:
    secret = _get_secret().encode('utf-8')
    message = f'{cmd}|{ts}|{nonce}'.encode('utf-8')
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def validate_signed_hostcmd_payload(
    payload: Any, seen_nonces: set[str], recent_nonces: deque[str]
) -> str | None:
    try:
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        if isinstance(payload, str):
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = payload
        else:
            logging.warning('Rejecting host command payload with unsupported type')
            return None
    except (UnicodeDecodeError, json.JSONDecodeError):
        logging.warning('Rejecting malformed host command payload')
        return None

    cmd = data.get('cmd')
    ts = data.get('ts')
    nonce = data.get('nonce')
    sig = data.get('sig')

    if not all([cmd, ts, nonce, sig]):
        logging.warning('Rejecting unsigned/incomplete host command payload')
        return None

    now = int(time.time())
    if abs(now - int(ts)) > COMMAND_MAX_AGE_SECONDS:
        logging.warning('Rejecting stale host command payload cmd=%s', cmd)
        return None

    if nonce in seen_nonces:
        logging.warning('Rejecting replayed host command payload cmd=%s', cmd)
        return None

    expected = sign_host_command(cmd=str(cmd), ts=int(ts), nonce=str(nonce))
    if not hmac.compare_digest(expected, str(sig)):
        logging.warning('Rejecting host command payload with invalid signature')
        return None

    seen_nonces.add(str(nonce))
    recent_nonces.append(str(nonce))
    while len(recent_nonces) > 2048:
        seen_nonces.discard(recent_nonces.popleft())

    return str(cmd)
