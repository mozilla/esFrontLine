# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
from __future__ import division
from __future__ import unicode_literals

import random
import time

import flask
import requests
from flask import Flask, json
from werkzeug.contrib.fixers import HeaderRewriterFix
from werkzeug.exceptions import abort

from esFrontLine.auth import HawkAuth, AUTH_EXCEPTION
from mo_dots import listwrap
from mo_future import BytesIO
from mo_logs import constants, Log, startup

settings = {}

app = Flask(__name__)
auth = HawkAuth()

DEBUG = False


def stream(raw_response):
    while True:
        block = raw_response.read(amt=65536, decode_content=False)
        if not block:
            return
        yield block


@app.route('/', defaults={'path': ''}, methods=['GET', 'HEAD', 'POST'])
@app.route('/<path:path>', methods=['GET', 'HEAD', 'POST'])
def catch_all(path):
    try:
        # Check HAWK authentication before processing request
        user_id = auth.check_user(flask.request)
        Log.note('Authenticated user {{user}}', user=user_id)

        data = flask.request.environ['body_copy']
        resource = filter(flask.request.method, path, data)

        # Check resource is allowed for current user
        if flask.request.method != 'HEAD':
            auth.check_resource(user_id, resource)

        #PICK RANDOM ES
        es = random.choice(listwrap(settings["elasticsearch"]))

        # SEND REQUEST
        headers = {k: v for k, v in flask.request.headers if v is not None and v != "" and v != "null"}
        headers['content-type'] = 'application/json'

        response = requests.request(
            flask.request.method,
            es["host"] + ":" + str(es["port"]) + "/" + path,
            data=data,
            stream=True,  # FOR STREAMING
            headers=headers,
            timeout=90
        )

        # ALLOW CROSS DOMAIN (BECAUSE ES IS USUALLY NOT ON SAME SERVER AS PAGE)
        outbound_header = dict(response.headers)
        outbound_header["access-control-allow-origin"] = "*"

        # LOG REQUEST TO ES
        request = flask.request
        uid = int(round(time.time() * 1000.0))
        slim_request = {
            "remote_addr": request.remote_addr,
            "method": request.method,
            "path": request.path,
            "request_length": len(data),
            "response_length": int(outbound_header["content-length"]) if "content-length" in outbound_header else None
        }
        try:
            requests.request(
                flask.request.method,
                es["host"] + ":" + str(es["port"]) + "/debug/esfrontline/"+str(uid),
                data=json.dumps(slim_request),
                timeout=5
            )
        except Exception as e:
            pass

        if DEBUG:
            Log.note(
                "path: {{path}}, request bytes={{request_content_length}}, response bytes={{response_content_length}}",
                path=path,
                # request_headers=dict(response.headers),
                request_content_length=len(data),
                # response_headers=outbound_header,
                response_content_length=int(outbound_header["content-length"]) if "content-length" in outbound_header else None
            )

        # FORWARD RESPONSE
        return flask.Response(
            stream(response.raw),
            direct_passthrough=True,  # FOR STREAMING
            status=response.status_code,
            headers=outbound_header
        )
    except Exception as e:
        Log.warning("Can not complete request", cause=e)
        if AUTH_EXCEPTION in e:
            abort(403)
        else:
            abort(400)


def filter(method, path_string, query):
    """
    THROW EXCEPTION IF THIS IS NOT AN ElasticSearch QUERY
    """
    try:
        if method.upper() == "HEAD":
            if path_string in ["", "/"]:
                return  # HEAD REQUESTS ARE ALLOWED
            else:
                Log.error("HEAD requests are generally not allowed")

        path = path_string.split("/")

        # EXPECTING {index_name} "/" {type_name} "/" {_id}
        # EXPECTING {index_name} "/" {type_name} "/_search"
        # EXPECTING {index_name} "/_search"
        es_methods = ["_mapping", "_search", "_count"]
        if len(path) == 2:
            if path[-1] not in es_methods:
                Log.error("request path must end with _mapping or _search")
        elif len(path) == 3:
            if path[-1] not in es_methods:
                Log.error("request path must end with _mapping or _search")
        else:
            Log.error('request must be of form: {index_name} "/" {type_name} "/_search" ')

        # COMPARE TO WHITE LIST
        if path[0] not in settings["whitelist"]:
            Log.error('index not in whitelist: {{index_name}}', index_name=path[0])


        # EXPECTING THE QUERY TO AT LEAST HAVE .query ATTRIBUTE
        if path[-1] == "_search" and json.loads(query).get("query", None) is None:
            Log.error("_search must have query")

        # NO CONTENT ALLOWED WHEN ASKING FOR MAPPING
        if path[-1] == "_mapping" and len(query) > 0:
            Log.error("Can not provide content when requesting _mapping")

    except Exception as e:
        Log.warning("Not allowed: {{path}}:\n{{query}}", path=path_string, query=query, cause=e)

    return path[0]


# Snagged from http://stackoverflow.com/questions/10999990/python-flask-how-to-get-whole-raw-post-body
# I SUSPECT THIS IS PREVENTING STREAMING
class WSGICopyBody(object):
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):

        length = environ.get('CONTENT_LENGTH', '0')
        length = 0 if length == '' else int(length)

        body = environ['wsgi.input'].read(length)
        environ['body_copy'] = body
        environ['wsgi.input'] = BytesIO(body)

        # Call the wrapped application
        app_iter = self.application(environ, self._sr_callback(start_response))

        # Return modified response
        return app_iter

    def _sr_callback(self, start_response):
        def callback(status, headers, exc_info=None):
            # Call upstream start_response
            start_response(status, headers, exc_info)

        return callback

settings = None
app.wsgi_app = WSGICopyBody(app.wsgi_app)

def main():
    global settings

    try:
        settings = startup.read_settings()
        constants.set(settings.constants)
        Log.start(settings.debug)

        # Setup auth users
        auth.load_users(settings.users)

        HeaderRewriterFix(app, remove_headers=['Date', 'Server'])
        app.run(**settings.flask)
    except Exception as e:
        Log.error("Problem with etl", e)
    finally:
        Log.stop()


if __name__ == '__main__':
    main()
