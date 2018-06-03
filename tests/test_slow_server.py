# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
import unittest

import requests

from esFrontLine.app import stream
from mo_logs import Log, startup
from mo_threads import Signal, Thread, Process
from mo_times import Timer

RUN_SLOW_SERVER = True
RUN_PROXY = True

WHITELISTED = "public_bugs"  # YOU MUST ENSURE THIS IS IN THE slow_server.json WHITELIST
PATH = '/'+WHITELISTED+'/_mapping'

server_is_ready = Signal()
proxy_is_ready = Signal()
settings = startup.read_settings(filename="tests/config/slow_server.json")


class TestSlowSever(unittest.TestCase):

    def test_slow_streaming(self):
        """
        TEST THAT THE app ACTUALLY STREAMS.  WE SHOULD GET A RESPONSE BEFORE THE SERVER
        FINISHES DELIVERING
        """
        slow_server_thread = Thread.run("run slow server", _run_slow_server)
        proxy_thread = Thread.run("run proxy", _run_esFrontline)

        try:
            proxy_is_ready.wait()
            server_is_ready.wait()

            with Timer("measure response times") as timer:
                response = requests.get("http://localhost:"+str(settings.flask.port)+PATH, stream=True)
                for i, data in enumerate(stream(response.raw)):
                    Log.note("CLIENT GOT RESPONSE:\n{{data|indent}}", {"data": data})
                    duration = timer.duration.seconds
                    if i == 0:
                        self.assertLess(duration, 10, "should have something by now")
                # self.assertEqual(response.status_code, 200, "Expecting a positive response")
            self.assertGreater(timer.duration.seconds, 10, "expecting slow server to talk a while")
        finally:
            slow_server_thread.please_stop.go()
            proxy_thread.please_stop.go()


def _run_slow_server(please_stop):
    if not RUN_SLOW_SERVER:
        server_is_ready.go()
        return

    proc = Process(
        "slow server",
        ["python", "tests/slow_server.py"],
        debug=True
    )

    while not please_stop:
        line = proc.stderr.pop().decode('utf8')
        if not line:
            continue
        if " * Running on" in line:
            server_is_ready.go()
        Log.note("SLOW SERVER: "+line)

    proc.stop()
    proc.join()


def _run_esFrontline(please_stop):
    if not RUN_PROXY:
        proxy_is_ready.go()
        return

    proc = Process(
        "slow server",
        ["python", "esFrontLine/app.py", "--config", "tests/config/slow_server.json"],
        debug=True
    )

    while not please_stop:
        line = proc.stderr.pop().decode('utf8')
        if not line:
            continue
        if " * Running on" in line:
            proxy_is_ready.go()
        Log.note("PROXY: {{line}}", {"line": line.strip()})

    proc.stop()
    proc.join()

