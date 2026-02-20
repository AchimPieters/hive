from __future__ import unicode_literals

import os
import unittest
from pathlib import Path

os.environ.setdefault('HOSTCMD_SIGNING_SECRET', 'test-secret')
os.environ.setdefault('ENVIRONMENT', 'test')

from celery_tasks import celery as celeryapp
from celery_tasks import cleanup


class CeleryTasksTestCase(unittest.TestCase):
    def setUp(self):
        celeryapp.conf.update(
            CELERY_ALWAYS_EAGER=True,
            CELERY_RESULT_BACKEND='',
            CELERY_BROKER_URL='',
        )


class TestCleanup(CeleryTasksTestCase):
    def setUp(self):
        super(TestCleanup, self).setUp()
        self.assets_path = Path(os.getenv('HOME')) / 'screenly_assets'
        self.assets_path.mkdir(parents=True, exist_ok=True)
        (self.assets_path / 'image.tmp').write_text('tmp')

    def test_cleanup(self):
        cleanup.apply()
        tmp_files = list(self.assets_path.rglob('*.tmp'))
        self.assertEqual(len(tmp_files), 0)
