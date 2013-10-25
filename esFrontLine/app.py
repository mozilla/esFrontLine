################################################################################
## This Source Code Form is subject to the terms of the Mozilla Public
## License, v. 2.0. If a copy of the MPL was not distributed with this file,
## You can obtain one at http://mozilla.org/MPL/2.0/.
################################################################################
## Author: Kyle Lahnakoski (kyle@lahnakoski.com)
################################################################################

from flask import Flask
import flask
import requests
from werkzeug.contrib.fixers import HeaderRewriterFix
from werkzeug.exceptions import abort
from esFrontLine.util import struct
from esFrontLine.util.randoms import Random
from esFrontLine.util.struct import Struct
from esFrontLine.util import startup
from esFrontLine.util.cnv import CNV
from esFrontLine.util.logs import Log


app = Flask(__name__)


def stream(raw_response):
    while True:
        block = raw_response.read(amt=65536, decode_content=False)
        if len(block) == 0:
            return
        yield block


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    try:
        data = flask.request.environ['body_copy']
        filter(path, data)

        #PICK RANDOM ES
        es = Random.sample(struct.listwrap(settings.elasticsearch), 1)[0]

        ## SEND REQUEST
        headers = {'content-type': 'application/json'}
        response = requests.get(
            es.host + ":" + str(es.port) + "/" + path,
            data=data,
            stream=True, #FOR STREAMING
            headers=headers,
            timeout=90
        )

        # ALLOW CROSS DOMAIN (BECAUSE ES IS USUALLY NOT ON SAME SERVER AS PAGE)
        outbound_header = dict(response.headers)
        outbound_header["access-control-allow-origin"] = "*"

        Log.println("path: {{path}}, request bytes={{request_content_length}}, response bytes={{response_content_length}}", {
            "path": path,
            "request_headers": dict(response.headers),
            "request_content_length": len(data),
            "response_headers": outbound_header,
            "response_content_length": outbound_header["content-length"]
        })

        ## FORWARD RESPONSE
        return flask.wrappers.Response(
            stream(response.raw),
            direct_passthrough=True, #FOR STREAMING
            status=response.status_code,
            headers=outbound_header
        )
    except Exception, e:
        Log.warning("processing problem", e)
        abort(400)

def filter(path_string, query):
    """
    THROW EXCEPTION IF THIS IS NOT AN ElasticSearch QUERY
    """
    try:
        path = path_string.split("/")

        ## EXPECTING {index_name} "/" {type_name} "/_search"
        ## EXPECTING {index_name} "/_search"
        if len(path) not in [2, 3]:
            Log.error("request must be of form:  {index_name} \"/\" {type_name} \"/_search\" ")
        if path[-1] not in ["_mapping", "_search"]:
            Log.error("request path must end with _mapping or _search")

        ## EXPECTING THE QUERY TO AT LEAST HAVE .query ATTRIBUTE
        if path[-1] == "_search" and CNV.JSON2object(query).query is None:
            Log.error("_search must have query")

        ## NO CONTENT ALLOWED WHEN ASKING FOR MAPPING
        if path[-1] == "_mapping" and len(query) > 0:
            Log.error("Can not provide content when requesting _mapping")

    except Exception, e:
        Log.error("Not allowed: {{path}}:\n{{query}}", {"path": path_string, "query": query}, e)


# Snagged from http://stackoverflow.com/questions/10999990/python-flask-how-to-get-whole-raw-post-body
# I SUSPECT THIS IS PREVENTING STREAMING
class WSGICopyBody(object):
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        from cStringIO import StringIO

        length = environ.get('CONTENT_LENGTH', '0')
        length = 0 if length == '' else int(length)

        body = environ['wsgi.input'].read(length)
        environ['body_copy'] = body
        environ['wsgi.input'] = StringIO(body)

        # Call the wrapped application
        app_iter = self.application(environ, self._sr_callback(start_response))

        # Return modified response
        return app_iter

    def _sr_callback(self, start_response):
        def callback(status, headers, exc_info=None):
            # Call upstream start_response
            start_response(status, headers, exc_info)

        return callback


app.wsgi_app = WSGICopyBody(app.wsgi_app)

if __name__ == '__main__':

    try:
        settings = startup.read_settings()
        Log.start(settings.debug)
        app.run(**settings.flask.dict)
        app = HeaderRewriterFix(app, remove_headers=['Date', 'Server'])
    finally:
        Log.println("Execution complete")
        Log.stop()