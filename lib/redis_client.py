import os
from typing import Any

import redis


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {'1', 'true', 'yes', 'on'}


def get_redis_connection_kwargs(decode_responses: bool = True) -> dict[str, Any]:
    redis_url = os.getenv('REDIS_URL')
    if redis_url:
        kwargs: dict[str, Any] = {
            'decode_responses': decode_responses,
            'health_check_interval': 30,
        }
        if _env_flag('REDIS_TLS') and redis_url.startswith('redis://'):
            redis_url = redis_url.replace('redis://', 'rediss://', 1)
        kwargs['from_url'] = redis_url
        return kwargs

    kwargs = {
        'host': os.getenv('REDIS_HOST', 'redis'),
        'port': int(os.getenv('REDIS_PORT', '6379')),
        'db': int(os.getenv('REDIS_DB', '0')),
        'password': os.getenv('REDIS_PASSWORD') or None,
        'decode_responses': decode_responses,
        'health_check_interval': 30,
    }

    if _env_flag('REDIS_TLS'):
        kwargs.update(
            {
                'ssl': True,
                'ssl_cert_reqs': os.getenv('REDIS_SSL_CERT_REQS', 'required'),
                'ssl_ca_certs': os.getenv('REDIS_SSL_CA_CERTS') or None,
            }
        )

    return kwargs


def connect_to_redis(decode_responses: bool = True):
    kwargs = get_redis_connection_kwargs(decode_responses=decode_responses)
    redis_url = kwargs.pop('from_url', None)
    if redis_url:
        return redis.Redis.from_url(redis_url, **kwargs)
    return redis.Redis(**kwargs)
