# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
from __future__ import division
from __future__ import unicode_literals

from mo_dots import wrap
from mohawk import Receiver
import random
import logging
import time

from mo_logs import Log


AUTH_EXCEPTION = "Authorization Exception: {{reason}}"


class HawkAuth(object):
    '''
    Authenticate users using HAWK protocol
    '''
    def __init__(self):
        self.users = []
        self.seen = {}

    def load_users(self, users):
        '''
        Load users from settings file, and validates their inner structure
        '''
        if not isinstance(users, list) or not len(users):
            return

        self.users = {}
        for index, user in enumerate(users):
            try:
                hawk = user.get('hawk')
                resources = user.get('resources')
                assert hawk is not None, 'Missing "hawk" setting in user config.'
                assert resources is not None, 'Missing "resources" setting in user config.'
                assert isinstance(resources, list), '"resources" must be JSON list'
                assert len(resources) > 0, '"resources" cannot be empty'
                assert isinstance(hawk, dict), '"hawk" must be a JSON dictionary'
                assert set(hawk.keys()) == {'algorithm', 'id', 'key'}, '"hawk" can only contains algorithm, id, key.'

                self.users[user['hawk']['id']] = user
                Log.note('Validated user {{user}}', user)
            except AssertionError as e:
                Log.error('Error on user {{user}}', user=user, cause=e)

        Log.note('Loaded {{num}} users', num=len(self.users))

    def check_user(self, request):
        '''
        Check HAWK authentication before processing the request
        '''
        if not self.users:
            Log.note('Authentication disabled')
            return

        if 'Authorization' not in request.headers:
            Log.error(AUTH_EXCEPTION, reason='Missing Auth header')

        # Check the hawk
        try:
            receiver = Receiver(
                self.lookup_user,
                request.headers['Authorization'],
                request.url,
                request.method,
                content=request.data,
                content_type=request.headers['Content-Type'],
                seen_nonce=self.build_nonce,
            )
            return receiver.parsed_header['id']
        except Exception as e:
            Log.error(AUTH_EXCEPTION, reason="unexpected", cause=e)



    def check_resource(self, user_id, resource):
        '''
        Check the resource is allowed by comparing with resources for the user
        '''
        if not self.users:
            Log.note('Authentication disabled')
            return

        user = self.users[user_id]
        if user is None:
            Log.error(AUTH_EXCEPTION, reason='Invalid user {}'.format(user_id))
        if resource not in user['resources']:
            Log.error(AUTH_EXCEPTION, reason= 'Resource {} not accessible for this user'.format(resource))

        return True

    def lookup_user(self, sender_id):
        '''
        Find user HAWK credentials in local users dict
        '''
        try:
            return self.users[sender_id]['hawk']
        except KeyError:
            raise LookupError

    def build_nonce(self, sender_id, nonce, timestamp):
        '''
        Avoid replay attacks by saving nonce+timestamp in memory
        https://mohawk.readthedocs.io/en/latest/usage.html#using-a-nonce-to-prevent-replay-attacks
        '''
        key = '{id}:{nonce}:{ts}'.format(
            id=sender_id,
            nonce=nonce,
            ts=timestamp
        )

        # Cleanup seen cache every once in a while
        if random.randint(0, 1000) == 0:
            old = time.time() - 3600
            self.seen = {k: v for k, v in self.seen.items() if v >= old}
            Log.note('Cleaned up Auth nonce cache')

        # Reject replay
        if self.seen.get(key):
            return True

        # Save nonce & allow request
        self.seen[key] = int(timestamp)
        return False
