from _subprocess import CREATE_NEW_PROCESS_GROUP
import subprocess
import requests
import signal
from util.logs import Log
from util.threads import Thread, Signal


def test_943465(url):
    #https://bugzilla.mozilla.org/show_bug.cgi?id=943465
    response = request("GET", url + "/_cluster/nodes/_local")
    if response.status_code != 400:
        Log.error("should not allow")

    response = request("GET", url + "/_cluster/nodes/stats")
    if response.status_code != 400:
        Log.error("should not allow")


def test_943472(url):
    #https://bugzilla.mozilla.org/show_bug.cgi?id=943472
    response = request("GET", url + "/bugs/_stats/")
    if response.status_code != 400:
        Log.error("should not allow")


def test_943478(url):
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

def test_allow_3path_mapping(url):
    #WE SHOULD ALLOW -mapping WITH INDEX AND TYPE IN PATH
    #http://klahnakoski-es.corp.tor1.mozilla.com:9204/bugs/bug_version/_mapping
    response = request("GET", url + "/bugs/bug_version/_mapping")
    if response.status_code != 200:
        Log.error("should be allowed")


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


def all_tests(url):
    test_943465(url)
    test_943472(url)
    test_943478(url)
    test_allow_3path_mapping(url)
    Log.note("ALL TESTS PASS")



def main():
    url = "http://localhost:9292"
    thread = Thread.run("run app", run_app)

    try:
        server_is_ready.wait_for_go()
        all_tests(url)
    finally:
        thread.please_stop.go()
        Log.stop()

if __name__=="__main__":
    main()
