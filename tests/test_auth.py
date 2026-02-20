import hashlib
from unittest import TestCase

from django.conf import settings as django_settings
from django.contrib.auth.hashers import make_password

from lib.auth import BasicAuth

if not django_settings.configured:
    django_settings.configure(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher']
    )


class DummySettings(dict):
    def save(self):
        self['saved'] = True


class BasicAuthTest(TestCase):
    def test_legacy_sha256_password_is_migrated(self):
        settings = DummySettings(
            user='admin',
            password=hashlib.sha256('secret'.encode('utf-8')).hexdigest(),
        )
        auth = BasicAuth(settings)
        self.assertTrue(auth.check_password('secret'))
        self.assertTrue(settings.get('saved'))
        self.assertNotEqual(len(settings['password']), 64)

    def test_modern_hash_is_checked(self):
        settings = DummySettings(user='admin', password=make_password('secret'))
        auth = BasicAuth(settings)
        self.assertTrue(auth.check_password('secret'))
        self.assertFalse(auth.check_password('bad'))
