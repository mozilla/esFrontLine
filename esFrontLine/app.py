# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
import argparse
import codecs
import logging
from logging.handlers import RotatingFileHandler
import os
import random
from flask import Flask, json
import flask
import requests
from werkzeug.contrib.fixers import HeaderRewriterFix
from werkzeug.exceptions import abort

app = Flask(__name__)


def stream(raw_response):
    while True:
        block = raw_response.read(amt=65536, decode_content=False)
        if not block:
            return
        yield block


def random_sample(data, count):
    num = len(data)
    return [data[random.randrange(num)] for i in range(count)]


def listwrap(value):
    if value == None:
        return []
    elif isinstance(value, list):
        return value
    else:
        return [value]


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    try:
        data = flask.request.environ['body_copy']
        filter(path, data)

        #PICK RANDOM ES
        es = random_sample(listwrap(settings["elasticsearch"]), 1)[0]

        ## SEND REQUEST
        headers = {'content-type': 'application/json'}
        response = requests.get(
            es["host"] + ":" + str(es["port"]) + "/" + path,
            data=data,
            stream=True, #FOR STREAMING
            headers=headers,
            timeout=90
        )

        # ALLOW CROSS DOMAIN (BECAUSE ES IS USUALLY NOT ON SAME SERVER AS PAGE)
        outbound_header = dict(response.headers)
        outbound_header["access-control-allow-origin"] = "*"
        logger.debug("path: {path}, request bytes={request_content_length}, response bytes={response_content_length}".format(
            path=path,
            # request_headers=dict(response.headers),
            request_content_length=len(data),
            # response_headers=outbound_header,
            response_content_length=outbound_header["content-length"]
        ))

        ## FORWARD RESPONSE
        return flask.wrappers.Response(
            stream(response.raw),
            direct_passthrough=True, #FOR STREAMING
            status=response.status_code,
            headers=outbound_header
        )
    except Exception, e:
        logger.warning("processing problem")
        logger.exception(e.message)
        abort(400)


def filter(path_string, query):
    """
    THROW EXCEPTION IF THIS IS NOT AN ElasticSearch QUERY
    """
    try:
        path = path_string.split("/")

        ## EXPECTING {index_name} "/" {type_name} "/" {_id}
        ## EXPECTING {index_name} "/" {type_name} "/_search"
        ## EXPECTING {index_name} "/_search"
        if len(path) == 2:
            if path[-1] not in ["_mapping", "_search"]:
                raise Exception("request path must end with _mapping or _search")
        elif len(path) == 3:
            pass  #OK
        else:
            raise Exception('request must be of form: {index_name} "/" {type_name} "/_search" ')

        ## EXPECTING THE QUERY TO AT LEAST HAVE .query ATTRIBUTE
        if path[-1] == "_search" and json.loads(query).get("query", None) is None:
            raise Exception("_search must have query")

        ## NO CONTENT ALLOWED WHEN ASKING FOR MAPPING
        if path[-1] == "_mapping" and len(query) > 0:
            raise Exception("Can not provide content when requesting _mapping")

    except Exception, e:
        logger.exception(e.message)
        raise Exception("Not allowed: {path}:\n{query}".format(path=path_string, query=query))


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

logger = None

if __name__ == '__main__':

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(*["--settings", "--settings-file", "--settings_file"], **{
            "help": "path to JSON file with settings",
            "type": str,
            "dest": "filename",
            "default": "./settings.json",
            "required": False
        })
        namespace = parser.parse_args()
        args = {k: getattr(namespace, k) for k in vars(namespace)}

        if not os.path.exists(args["filename"]):
            raise Exception("Can not file settings file {filename}".format(filename=args["filename"]))

        with codecs.open(args["filename"], "r", encoding="utf-8") as file:
            json_data = file.read()
        settings = json.loads(json_data)
        settings["args"] = args

        logger = logging.getLogger('esFrontLine')
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        for d in listwrap(settings["debug"]["log"]):
            if d.get("filename", None):
                fh = RotatingFileHandler(**d)
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(formatter)
                logger.addHandler(fh)
            elif d.get("stream", None) == "sys.stdout":
                ch = logging.StreamHandler()
                ch.setLevel(logging.DEBUG)
                ch.setFormatter(formatter)
                logger.addHandler(ch)

        HeaderRewriterFix(app, remove_headers=['Date', 'Server'])
        app.run(**settings["flask"])
    except Exception, e:
        print(e.message)
