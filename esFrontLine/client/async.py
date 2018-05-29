# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#

from elasticsearch_async.connection import AIOHttpConnection
from esFrontLine.client.base import BaseHawkConnection


class AsyncHawkConnection(BaseHawkConnection, AIOHttpConnection):
    '''
    Connection class to use with an elasticsearch asynchronous python client
    '''

    async def perform_request(self, method, url, params=None, body=None, timeout=None, ignore=(), headers=None):
        '''
        Build a new HAWK header on each request
        Using elasticsearch Asynchronous client
        '''
        hawk_headers = self.add_hawk_authentication(method, url, params, body, headers)
        return await super().perform_request(method, url, params, body, timeout, ignore, headers=hawk_headers)
