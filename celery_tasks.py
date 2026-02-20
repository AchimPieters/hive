import logging
from datetime import timedelta
from os import environ, getenv, path
from pathlib import Path

import django
from celery import Celery
from tenacity import Retrying, stop_after_attempt, wait_fixed

from lib.host_commands import build_signed_hostcmd_payload
from lib.redis_client import connect_to_redis

environ.setdefault('DJANGO_SETTINGS_MODULE', 'hive_django.settings')

try:
    django.setup()
except Exception:
    logging.exception('Failed to initialize Django for Celery worker')
    raise

from lib import diagnostics
from lib.utils import (
    is_balena_app,
    reboot_via_balena_supervisor,
    shutdown_via_balena_supervisor,
)


__author__ = 'HIVE, Inc'
__copyright__ = 'Copyright 2012-2024, HIVE, Inc'
__license__ = 'Dual License: GPLv2 and Commercial License'


def _get_celery_url(env_name, dev_default):
    value = getenv(env_name)
    environment = getenv('ENVIRONMENT', 'development')
    if environment not in {'development', 'test'} and not value:
        raise RuntimeError(f'{env_name} must be configured outside development/test')
    return value or dev_default


CELERY_RESULT_BACKEND = _get_celery_url(
    'CELERY_RESULT_BACKEND', 'redis://redis:6379/0'
)
CELERY_BROKER_URL = _get_celery_url('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_TASK_RESULT_EXPIRES = timedelta(hours=6)

r = connect_to_redis()
celery = Celery(
    'HIVE Celery Worker',
    backend=CELERY_RESULT_BACKEND,
    broker=CELERY_BROKER_URL,
    result_expires=CELERY_TASK_RESULT_EXPIRES,
)


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(3600, cleanup.s(), name='cleanup')
    sender.add_periodic_task(60 * 5, get_display_power.s(), name='display_power')


@celery.task(time_limit=30)
def get_display_power():
    r.set('display_power', diagnostics.get_display_power())
    r.expire('display_power', 3600)


@celery.task
def cleanup():
    assets_path = Path(path.join(getenv('HOME'), 'screenly_assets'))
    for tmp_file in assets_path.rglob('*.tmp'):
        try:
            tmp_file.unlink()
        except OSError:
            logging.exception('Failed deleting temporary file: %s', tmp_file)


@celery.task
def reboot_anthias():
    if is_balena_app():
        for attempt in Retrying(stop=stop_after_attempt(5), wait=wait_fixed(1)):
            with attempt:
                reboot_via_balena_supervisor()
    else:
        r.publish('hostcmd', build_signed_hostcmd_payload('reboot'))


@celery.task
def shutdown_anthias():
    if is_balena_app():
        for attempt in Retrying(stop=stop_after_attempt(5), wait=wait_fixed(1)):
            with attempt:
                shutdown_via_balena_supervisor()
    else:
        r.publish('hostcmd', build_signed_hostcmd_payload('shutdown'))
