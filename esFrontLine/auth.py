from mohawk import Receiver
import random
import logging
import time


logger = logging.getLogger('esFrontLine')

class AuthException(Exception):
    '''
    Exception occuring during the authentication protocol
    '''


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

        def _valid_user(user):
            # Check each user structure from settings
            hawk = user.get('hawk')
            resources = user.get('resources')
            if hawk is None or resources is None:
                return False

            if not isinstance(resources, list) or not isinstance(hawk, dict):
                return False

            if hawk.keys() != ['algorithm', 'id', 'key']:
                return False

            logger.debug('Validated user {id}'.format(**user['hawk']))
            return user

        self.users = {
            user['hawk']['id']: user
            for user in filter(_valid_user, users)
        }
        logger.info('Loaded {} users'.format(len(self.users)))

    def check(self, request, resource):
        '''
        Check HAWK authentication before processing the request
        '''
        if not self.users:
            logger.info('Authentication disabled')
            return

        if 'Authorization' not in request.headers:
            raise AuthException('Missing Auth header')

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
        except Exception as e:
            raise AuthException(str(e))

        # Check the resource is allowed by comparing with resources for the user
        user = self.users[receiver.parsed_header['id']]
        if resource not in user['resources']:
            raise AuthException('Resource {} not accessible for this user'.format(resource))

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
            logger.info('Cleaned up Auth nonce cache')

        # Reject replay
        if self.seen.get(key):
            return True

        # Save nonce & allow request
        self.seen[key] = int(timestamp)
        return False
