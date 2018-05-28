# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#

from elasticsearch.connection import Urllib3HttpConnection
from esFrontLine.client.base import BaseHawkConnection


class HawkConnection(BaseHawkConnection, Urllib3HttpConnection):
    '''
    Connection class to use with an elasticsearch synchronous python client
    '''

    def perform_request(self, method, url, params, body, headers=None, *args, **kwargs):
        '''
        Build a new HAWK header on each request
        Using elasticsearch Synchronous client
        '''
        hawk_headers = self.add_hawk_authentication(method, url, params, body, headers)

        # This calling style is compatible with both Python 2 and 3
        return Urllib3HttpConnection.perform_request(self, method, url, params, body, headers=hawk_headers, *args, **kwargs)
