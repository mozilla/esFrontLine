import unittest

import requests
from mo_dots import listwrap
from mo_future import text_type

from mo_logs import Log, constants, startup
from mo_threads import Signal, Process, Thread


class TestByBug(unittest.TestCase):
    app = None
    whiltelisted = None  # ENSURE THIS IS IN THE test_settings.json WHITELIST
    NOT_WHITELISTED = "this-is-not-an-index"
    url = None


    @classmethod
    def setUpClass(cls):
        TestByBug.app = Thread.run("run app", run_app)

        # PEEK AT SERVER CONFIG TO GET TEST PARAMETERS
        settings = startup.read_settings(filename="tests/config/test_settings.json")
        constants.set(settings.constants)
        Log.start(settings.debug)

        TestByBug.url = "http://localhost:" + text_type(settings.flask.port)
        TestByBug.whiltelisted = listwrap(settings.whiltelist)[0]

    @classmethod
    def tearDownClass(cls):
        TestByBug.app.stop()
        TestByBug.app.join()

    def test_943465(self):
        # https://bugzilla.mozilla.org/show_bug.cgi?id=943465
        response = request("GET", self.url + "/_cluster/nodes/_local")
        if response.status_code != 400:
            Log.error("should not allow")

        response = request("GET", self.url + "/_cluster/nodes/stats")
        if response.status_code != 400:
            Log.error("should not allow")

    def test_943472(self):
        # https://bugzilla.mozilla.org/show_bug.cgi?id=943472
        response = request("GET", self.url + "/" + self.whiltelisted + "/_stats/")
        if response.status_code != 400:
            Log.error("should not allow")

    def test_943478(self):
        # https://bugzilla.mozilla.org/show_bug.cgi?id=943478
        response = request("POST", self.url + "/" + self.NOT_WHITELISTED + "/_search", data="""
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
        response = request("POST", self.url + "/" + self.whiltelisted + "/_search", data="""
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
        # WE SHOULD ALLOW -mapping WITH INDEX AND TYPE IN PATH
        # http://klahnakoski-es.corp.tor1.mozilla.com:9204/bugs/bug_version/_mapping
        response = request("GET", self.url + "/" + self.whitelisted + "/bug_version/_mapping")
        if response.status_code != 200:
            Log.error("should be allowed")

    def test_allow_head_request(self):
        # WE SHOULD ALLOW HEAD REQUESTS TO /
        response = request("HEAD", self.url + "/")
        if response.status_code != 200:
            Log.error("should be allowed")

        response = request("HEAD", self.url)
        if response.status_code != 200:
            Log.error("should be allowed")

        # EVEN HEAD REQUESTS TO WHITELISTED INDEXES WILL BE DENIED
        response = request("HEAD", self.url + "/" + self.whitelisted + "/bug_version/_mapping")
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
        ["python", "esFrontLine\\app.py", "--settings", "tests/config/test_settings.json"],
        debug=True
    )

    while not please_stop:
        line = proc.stderr.pop().decode('utf8')
        if not line:
            continue
        if " * Running on" in line:
            server_is_ready.go()
        Log.note("SERVER: {{line}}", {"line": line.strip()})

    proc.stop()
    proc.join()


