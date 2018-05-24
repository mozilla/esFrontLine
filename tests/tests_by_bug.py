import unittest

import requests

from mo_logs import Log
from mo_threads import Signal, Process, Thread

WHITELISTED = "public_bugs"  # ENSURE THIS IS IN THE test_settings.json WHITELIST
NOT_WHITELISTED = "bug_hierarchy"

url = "http://localhost:9292"


class TestByBug(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        TestByBug.app = Thread.run("run app", run_app)

    @classmethod
    def tearDownClass(cls):
        TestByBug.app.stop()
        TestByBug.app.join()

    def test_943465(self):
        # https://bugzilla.mozilla.org/show_bug.cgi?id=943465
        response = request("GET", url + "/_cluster/nodes/_local")
        if response.status_code != 400:
            Log.error("should not allow")

        response = request("GET", url + "/_cluster/nodes/stats")
        if response.status_code != 400:
            Log.error("should not allow")

    def test_943472(self):
        # https://bugzilla.mozilla.org/show_bug.cgi?id=943472
        response = request("GET", url + "/" + WHITELISTED + "/_stats/")
        if response.status_code != 400:
            Log.error("should not allow")

    def test_943478(self):
        # https://bugzilla.mozilla.org/show_bug.cgi?id=943478
        response = request("POST", url + "/" + NOT_WHITELISTED + "/_search", data="""
        {
            "query":{"filtered":{
                "query":{"match_all":{}}
            }},
            "from":0,
            "size":0,
            "sort":[],
            "facets":{"default":{"terms":{"field":"info.OS","size":200000}}}
        }""")
        if response.status_code != 400:
            Log.error("should not allow")

        # VERIFY ALLOWED INDEX GETS THROUGH
        response = request("POST", url + "/" + WHITELISTED + "/_search", data="""
        {
            "query":{"filtered":{
                "query":{"match_all":{}},
                "filter":{"range":{"bug_id":{"lt":700000}}}
            }},
            "from":0,
            "size":0,
            "sort":[],
            "facets":{"default":{"terms":{"field":"product","size":200000}}}
        }""")
        if response.status_code != 200:
            Log.error("query should work")

    def test_allow_3path_mapping(self):
        #WE SHOULD ALLOW -mapping WITH INDEX AND TYPE IN PATH
        #http://klahnakoski-es.corp.tor1.mozilla.com:9204/bugs/bug_version/_mapping
        response = request("GET", url + "/" + WHITELISTED + "/bug_version/_mapping")
        if response.status_code != 200:
            Log.error("should be allowed")

    def test_allow_head_request(self):
        # WE SHOULD ALLOW HEAD REQUESTS TO /
        response = request("HEAD", url + "/")
        if response.status_code != 200:
            Log.error("should be allowed")

        response = request("HEAD", url)
        if response.status_code != 200:
            Log.error("should be allowed")

        # EVEN HEAD REQUESTS TO WHITELISTED INDEXES WILL BE DENIED
        response = request("HEAD", url + "/" + WHITELISTED + "/bug_version/_mapping")
        if response.status_code == 200:
            Log.error("should NOT be allowed")


def request(type, url, data=None, **kwargs):
    Log.note("CLIENT REQUEST: {{type}} {{url}} data={{data|newline|indent}}", {
        "type": type,
        "url": url,
        "data": data,
        "args": kwargs
    })
    response = requests.request(type, url, data=data, **kwargs)
    Log.note("CLIENT GOT RESPONSE: {{status_code}}\n{{text|indent}}", {
        "status_code": response.status_code,
        "text": response.text
    })
    return response


server_is_ready = Signal()


def run_app(please_stop):
    proc = Process(
        "app",
        ["python", "esFrontLine\\app.py", "--settings", "tests/resources/test_settings.json"],
        debug=True
    )

    while not please_stop:
        line = proc.stderr.readline().decode('utf8')
        if not line:
            continue
        if " * Running on" in line:
            server_is_ready.go()
        Log.note("SERVER: {{line}}", {"line": line.strip()})

    proc.stop()
    proc.join()


