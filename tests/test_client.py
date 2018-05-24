# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
from __future__ import division
from __future__ import unicode_literals

import json
import unittest

import elasticsearch

from esFrontLine.connection import HawkConnection
from mo_dots import listwrap
from mo_logs import startup, constants, Log
from mo_threads import Process


class TestClient(unittest.TestCase):

    settings = None
    server = None

    @staticmethod
    def setUpClass():
        settings = TestClient.settings = startup.read_settings(filename="tests/config/client.json")
        constants.set(settings.constants)
        Log.start(settings.debug)
        server = TestClient.server = Process(
            "server",
            ["python", "esFrontLine/app.py", "--config=tests/config/server.json"],
            debug=True
        )
        while True:
            line = server.stderr.pop().decode('utf8')
            if " * Running on " in line:
                break


    @staticmethod
    def tearDownClass():
        TestClient.server.stop()
        TestClient.server.join()


    def test_simple(self):

        es = elasticsearch.Elasticsearch(
            hosts=[TestClient.settings.elasticsearch],
            connection_class=HawkConnection,
            hawk_credentials=TestClient.settings.user.hawk
        )
        es.ping()
        for table in listwrap(TestClient.settings.tables):
            print('Count: {}'.format(es.count(index=table)))
            response = es.search(index=table, body={'query': {"match_all": {}}, "size": 0})
            print('Response:\n{}'.format(json.dumps(response, sort_keys=True, indent=4)))


