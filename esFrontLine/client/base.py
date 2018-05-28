# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#

from collections import Mapping
from mohawk import Sender
from elasticsearch.compat import urlencode

class BaseHawkConnection(object):

    def __init__(self, hawk_credentials=None, *args, **kwargs):
        super(BaseHawkConnection, self).__init__(*args, **kwargs)

        # Save credentials
        assert isinstance(hawk_credentials, Mapping), 'hawk_credentials should be a dict'
        assert set(hawk_credentials.keys()) == {'algorithm', 'id', 'key'}, 'hawk_credentials can only contains algorithm, id, key.'
        self._hawk_credentials = hawk_credentials

    def add_hawk_authentication(self, method, url, params, body, headers=None):
        # Build full url as in Urllib3HttpConnection
        local_url = self.url_prefix + url
        if params:
            local_url = '%s?%s' % (url, urlencode(params))
        full_url = self.host + local_url

        # Get content type from both headers source
        if headers and 'content-type' in headers:
            content_type = headers['content-type']
        elif hasattr(self, 'headers'):
            content_type = self.headers.get('content-type', 'application/json')
        else:
            content_type = 'application/json'

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

        return hawk_headers
