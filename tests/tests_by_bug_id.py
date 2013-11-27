from _subprocess import CREATE_NEW_PROCESS_GROUP
import os
import subprocess
import requests
import signal
from util.logs import Log
from util.threads import Thread, Signal


url = "http://localhost:9292"
# url = "http://klahnakoski-es.corp.tor1.mozilla.com:9292"


def test_943465():
    #https://bugzilla.mozilla.org/show_bug.cgi?id=943465
    response = request("GET", url + "/_cluster/nodes/_local")
    if response.status_code != 400:
        Log.error("should not allow")

    response = request("GET", url + "/_cluster/nodes/stats")
    if response.status_code != 400:
        Log.error("should not allow")


def test_943472():
    #https://bugzilla.mozilla.org/show_bug.cgi?id=943472
    response = request("GET", url + "/bugs/_stats/")
    if response.status_code != 400:
        Log.error("should not allow")


def test_943478():
    #https://bugzilla.mozilla.org/show_bug.cgi?id=943478
    response = request("POST", url + "/telemetry_agg_valid_201302/_search", data="""
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
    response = request("POST", url + "/bugs/_search", data="""
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


def request(type, url, data=None, **kwargs):
    Log.note("CLIENT REQUEST: {{type}} {{url}} data={{data|newline|indent}}", {
        "type": type,
        "url": url,
        "data": data,
        "args": kwargs
    })
    response = requests.request(type, url, data=data, **kwargs)
    Log.note("CLIENT RESPONSE: {{status_code}}\n{{text|indent}}", {
        "status_code": response.status_code,
        "text": response.text
    })
    return response


server_is_ready = Signal()


def run_app(please_stop):
    proc = subprocess.Popen(
        ["python", "esFrontLine\\app.py", "--settings", "tests/resources/test_settings.json"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=-1,
        creationflags=CREATE_NEW_PROCESS_GROUP
    )

    while not please_stop:
        line = proc.stdout.readline()
        if not line:
            continue
        if line.find(" * Running on") >= 0:
            server_is_ready.go()
        Log.note("SERVER: {{line}}", {"line": line.strip()})

    proc.send_signal(signal.CTRL_C_EVENT)


thread = Thread.run("run app", run_app)
try:
    server_is_ready.wait_for_go()
    test_943465()
    test_943472()
    test_943478()
    Log.note("ALL TESTS PASS")
finally:
    thread.please_stop.go()
    Log.stop()
