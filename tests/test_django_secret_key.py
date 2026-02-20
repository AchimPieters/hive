import importlib
import os
import sys
from unittest import TestCase


class DjangoSecretKeyTest(TestCase):
    def test_production_requires_secret_key(self):
        old_env = os.environ.copy()
        os.environ['ENVIRONMENT'] = 'production'
        os.environ.pop('DJANGO_SECRET_KEY', None)
        sys.modules.pop('hive_django.settings', None)
        with self.assertRaises(RuntimeError):
            importlib.import_module('hive_django.settings')
        os.environ.clear()
        os.environ.update(old_env)
