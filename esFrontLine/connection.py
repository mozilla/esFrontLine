from mohawk import Sender
from elasticsearch.connection import Urllib3HttpConnection
from elasticsearch.compat import urlencode


class HawkConnection(Urllib3HttpConnection):
    '''
    Connection class to use with an elasticsearch python client
    '''

    def __init__(self, hawk_credentials=None, *args, **kwargs):
        super(HawkConnection, self).__init__(*args, **kwargs)

        # Save credentials
        assert isinstance(hawk_credentials, dict), 'hawk_credentials should be a dict'
        assert {'algorithm', 'id', 'key'}.symmetric_difference(hawk_credentials.keys()) == set(), \
            'hawk_credentials can only contains algorithm, id, key.'
        self._hawk_credentials = hawk_credentials

    def perform_request(self, method, url, params, body, headers=None, *args, **kwargs):
        '''
        Build a new HAWK header on each request
        '''
        # Build full url as in Urllib3HttpConnection
        url = self.url_prefix + url
        if params:
            url = '%s?%s' % (url, urlencode(params))
        full_url = self.host + url

        # Get content type from both headers source
        if headers and 'content-type' in headers:
            content_type = headers['content-type']
        else:
            content_type = self.headers.get('content-type', 'application/json')

        # Build HAWK header
        sender = Sender(
            self._hawk_credentials,
            full_url,
            method,
            body or '', # mohawk always needs a body
            content_type=content_type,
        )

        # Apply to request headers
        hawk_headers = headers and headers.copy() or {}
        hawk_headers['Authorization'] = sender.request_header

        return super(HawkConnection, self).perform_request(method, url, params, body, headers=hawk_headers, *args, **kwargs)
