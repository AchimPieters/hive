#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

__author__ = 'Nash Kaminski'
__license__ = 'Dual License: GPLv2 and Commercial License'

import ipaddress
import json
import logging
import os
import subprocess

import time
from collections import deque

from lib.host_commands import (
    HOSTCMD_RATE_LIMIT_SECONDS,
    validate_signed_hostcmd_payload,
)
from lib.redis_client import connect_to_redis

import netifaces
import requests
from tenacity import (
    RetryError,
    Retrying,
    stop_after_attempt,
    wait_fixed,
)

# Name of redis channel to listen to
CHANNEL_NAME = b'hostcmd'
RATE_LIMITED_COMMANDS = {'reboot', 'shutdown'}
LAST_COMMAND_TS = {}
SEEN_NONCES = set()
RECENT_NONCES = deque()

SUPPORTED_INTERFACES = (
    'wlan',
    'eth',
    'wlp',
    'enp',
    'eno',
)


def get_ip_addresses():
    return [
        ip['addr']
        for interface in netifaces.interfaces()
        if interface.startswith(SUPPORTED_INTERFACES)
        for ip in (
            netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
            + netifaces.ifaddresses(interface).get(netifaces.AF_INET6, [])
        )
        if not ipaddress.ip_address(ip['addr']).is_link_local
    ]


def set_ip_addresses():
    rdb = connect_to_redis(decode_responses=False)

    rdb.set('ip_addresses_ready', 'false')

    try:
        for attempt in Retrying(
            stop=stop_after_attempt(10),
            wait=wait_fixed(1),
        ):
            with attempt:
                response = requests.get('https://1.1.1.1')
                response.raise_for_status()
    except RetryError:
        logging.warning(
            'Unable to connect to the Internet. '
            'Proceeding with the current IP addresses available.'
        )

    rdb.set('ip_addresses_ready', 'true')

    ip_addresses = get_ip_addresses()
    rdb.set('ip_addresses', json.dumps(ip_addresses))


# Explicit command whitelist for security reasons, keys as bytes objects
CMD_TO_ARGV = {
    b'reboot': ['/usr/bin/sudo', '-n', '/usr/bin/systemctl', 'reboot'],
    b'shutdown': ['/usr/bin/sudo', '-n', '/usr/bin/systemctl', 'poweroff'],
    b'set_ip_addresses': set_ip_addresses,
}


def execute_host_command(cmd_name):
    cmd = CMD_TO_ARGV.get(cmd_name, None)
    if cmd is None:
        logging.warning(
            'Unable to perform host command %s: no such command!', cmd_name
        )
    elif os.getenv('TESTING'):
        logging.warning(
            'Would have executed %s but not doing so as TESTING is defined',
            cmd,
        )
    elif cmd_name in [b'reboot', b'shutdown']:
        logging.info('Executing host command %s', cmd_name)
        try:
            phandle = subprocess.run(
                cmd,
                check=True,
                timeout=10,
                capture_output=True,
                text=True,
            )
            logging.info(
                'Host command %s completed rc=%s stdout=%s stderr=%s',
                cmd_name,
                phandle.returncode,
                (phandle.stdout or '')[:500],
                (phandle.stderr or '')[:500],
            )
        except subprocess.CalledProcessError as exc:
            logging.error(
                'Host command %s failed rc=%s stdout=%s stderr=%s',
                cmd_name,
                exc.returncode,
                (exc.stdout or '')[:500],
                (exc.stderr or '')[:500],
            )
        except subprocess.TimeoutExpired as exc:
            logging.error('Host command %s timed out after %s seconds', cmd_name, exc.timeout)
    else:
        logging.info('Calling function %s', cmd)
        cmd()


def process_message(message):
    if (
        message.get('type', '') == 'message'
        and message.get('channel', b'') == CHANNEL_NAME
    ):
        cmd_name = validate_signed_hostcmd_payload(
            message.get('data', b''),
            seen_nonces=SEEN_NONCES,
            recent_nonces=RECENT_NONCES,
        )
        if not cmd_name:
            return

        now = int(time.time())
        if cmd_name in RATE_LIMITED_COMMANDS:
            last_run = LAST_COMMAND_TS.get(cmd_name, 0)
            if now - last_run < HOSTCMD_RATE_LIMIT_SECONDS:
                logging.warning(
                    'Rate limit reject for host command %s (last=%s, window=%s)',
                    cmd_name,
                    last_run,
                    HOSTCMD_RATE_LIMIT_SECONDS,
                )
                return
            LAST_COMMAND_TS[cmd_name] = now

        execute_host_command(cmd_name.encode('utf-8'))
    else:
        logging.info('Received unsolicited message: %s', message)


def subscriber_loop():
    # Connect to redis on localhost and wait for messages
    logging.info('Connecting to redis...')
    rdb = connect_to_redis(decode_responses=False)
    pubsub = rdb.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(CHANNEL_NAME)
    rdb.set('host_agent_ready', 'true')
    logging.info(
        'Subscribed to channel %s, ready to process messages', CHANNEL_NAME
    )
    for message in pubsub.listen():
        process_message(message)


if __name__ == '__main__':
    # Init logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    # Loop forever processing messages
    subscriber_loop()
