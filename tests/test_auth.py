import unittest
import logging
import responses
import re
from esFrontLine import app as frontline
from esFrontLine.auth import HawkAuth
from mohawk import Sender

VALID_USER = {
    "id": "babadie@mozilla.com",
    "key": "dummySecret",
    "algorithm": "sha256"
}

INVALID_USER = {
    "id": "babadie@mozilla.com",
    "key": "INVALID_SECRET",
    "algorithm": "sha256"
}


def mock_hawk(method, url='/', body='', user=VALID_USER):
    '''
    Helper to create an HAWK header towards mock server
    '''
    full_url = 'http://localhost' + url
    sender = Sender(user, full_url, method, body, content_type='application/json')
    return {
        'Authorization': sender.request_header,
        'Content-Type': 'application/json',
    }


class TestAuthentication(unittest.TestCase):
    '''
    Test the authentication process through Hawk
    '''
    def setUp(self):
        logging.basicConfig()

        # Setup test settings
        frontline.settings = {
            'whitelist': ['test-index', 'protected-data', ],
            'elasticsearch': [{
                "host":"http://unittest",
                "port":9200
            }],
        }
        frontline.auth.load_users([{
          "hawk": VALID_USER,
          "resources": ['test-index', ],
        }])

        # Setup flask app Client
        frontline.app.testing = True
        self.client = frontline.app.test_client()

        # Setup responses
        mock_es = re.compile('http://unittest:9200/.*')
        responses.add(
            responses.GET,
            mock_es,
            body='{}',
            content_type='application/json',
            status=400
        )
        responses.add(
            responses.GET,
            mock_es,
            body='{"query":{}}',
            content_type='application/json',
            status=200
        )
        responses.add(
            responses.HEAD,
            mock_es,
            body='',
            content_type='application/json',
        )

    @responses.activate
    def test_head(self):
        '''
        HEAD request should always work when authenticated
        '''

        # No auth
        r = self.client.head('/')
        self.assertEqual(r.status_code, 403)

        # Invalid auth
        r = self.client.head('/', headers={'Authorization': 'Invalid token'})
        self.assertEqual(r.status_code, 403)

        # Valid auth
        valid_hawk = mock_hawk('HEAD')
        r = self.client.head('/', headers=valid_hawk)
        self.assertEqual(r.status_code, 200)

        # Replay not allowed
        r = self.client.head('/', headers=valid_hawk)
        self.assertEqual(r.status_code, 403)

        # Invalid secret
        invalid_hawk = mock_hawk('HEAD', user=INVALID_USER)
        r = self.client.head('/', headers=invalid_hawk)
        self.assertEqual(r.status_code, 403)

    @responses.activate
    def test_get(self):
        '''
        Test some GET requests with authentication
        '''
        search_url = '/test-index/_search'

        # No auth, no query
        r = self.client.get(search_url )
        self.assertEqual(r.status_code, 403)

        # Valid auth but missing query
        valid_hawk = mock_hawk('GET', search_url, '{}')
        r = self.client.get(search_url, data='{}', headers=valid_hawk)
        self.assertEqual(r.status_code, 400)

        # Valid auth + query
        valid_hawk = mock_hawk('GET', search_url, '{"query":{}}')
        r = self.client.get(search_url, data='{"query":{}}', headers=valid_hawk)
        self.assertEqual(r.status_code, 200)


    @responses.activate
    def test_get_on_restricted_index(self):
        '''
        Test some GET requests with authentication
        '''
        search_url = '/not-allowed/_search'

        # Valid auth + query
        valid_hawk = mock_hawk('GET', search_url, '{"query":{}}')
        r = self.client.get(search_url, data='{"query":{}}', headers=valid_hawk)
        self.assertEqual(r.status_code, 403)


    @responses.activate
    def test_user_syntax(self):
        '''
        Test user syntax from settings
        '''
        auth = HawkAuth()
        self.assertEqual(len(auth.users), 0)

        # Missing hawk
        with self.assertRaises(Exception) as e:
            auth.load_users([{
                'user': 'test',
            }])
        self.assertIn('Missing "hawk" setting in user config.', e.exception)
        self.assertEqual(len(auth.users), 0)

        # Missing resources
        with self.assertRaises(Exception) as e:
            auth.load_users([{
                'hawk': 'test',
            }])
        self.assertIn('Missing "resources" setting in user config.', e.exception)
        self.assertEqual(len(auth.users), 0)

        # Resources not a list
        with self.assertRaises(Exception) as e:
            auth.load_users([{
                'hawk': 'test',
                'resources': 'test',
            }])
        self.assertIn('"resources" must be JSON list', e.exception)
        self.assertEqual(len(auth.users), 0)

        # hawk not a dict
        with self.assertRaises(Exception) as e:
            auth.load_users([{
                'hawk': 'test',
                'resources': ['test'],
            }])
        self.assertIn('"hawk" must be a JSON dictionary', e.exception)
        self.assertEqual(len(auth.users), 0)

        # Invalid hawk
        with self.assertRaises(Exception) as e:
            auth.load_users([{
                'hawk': {},
                'resources': ['test'],
            }])
        self.assertIn('"hawk" can only contains algorithm, id, key.', e.exception)
        self.assertEqual(len(auth.users), 0)

        # Valid hawk
        auth.load_users([{
            'hawk': {
                'algorithm': 'sha1',
                'id': 'testId',
                'key': 'testKey',
            },
            'resources': ['test'],
        }])
        self.assertEqual(len(auth.users), 1)

if __name__ == '__main__':
    unittest.main()
