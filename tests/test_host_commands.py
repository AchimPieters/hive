import json
import os
from collections import deque
from unittest import TestCase
from unittest.mock import patch

from lib.host_commands import (
    build_signed_hostcmd_payload,
    validate_signed_hostcmd_payload,
)


class HostCommandSecurityTest(TestCase):
    def setUp(self):
        os.environ['HOSTCMD_SIGNING_SECRET'] = 'test-secret'

    def test_signed_payload_is_accepted(self):
        payload = build_signed_hostcmd_payload('reboot')
        cmd = validate_signed_hostcmd_payload(payload, set(), deque())
        self.assertEqual(cmd, 'reboot')

    def test_replayed_nonce_is_rejected(self):
        payload = json.loads(build_signed_hostcmd_payload('shutdown'))
        seen = set()
        recent = deque()
        self.assertEqual(
            validate_signed_hostcmd_payload(payload, seen, recent), 'shutdown'
        )
        self.assertIsNone(validate_signed_hostcmd_payload(payload, seen, recent))

    def test_stale_timestamp_is_rejected(self):
        payload = json.loads(build_signed_hostcmd_payload('reboot'))
        with patch('lib.host_commands.time.time', return_value=payload['ts'] + 3600):
            self.assertIsNone(
                validate_signed_hostcmd_payload(payload, set(), deque())
            )
