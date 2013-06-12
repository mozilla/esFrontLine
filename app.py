################################################################################
## This Source Code Form is subject to the terms of the Mozilla Public
## License, v. 2.0. If a copy of the MPL was not distributed with this file,
## You can obtain one at http://mozilla.org/MPL/2.0/.
################################################################################
## Author: Kyle Lahnakoski (kyle@lahnakoski.com)
################################################################################
from string import Template

from flask import Flask
import flask
import requests
from werkzeug.contrib.fixers import HeaderRewriterFix
from werkzeug.exceptions import abort
from util.startup import startup
from util.cnv import CNV
from util.debug import D


app = Flask(__name__)


# READ SETTINGS
settings=startup.read_settings()


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    try:
        data = flask.request.environ['body_copy']
        filter(path, data)

        ## SEND REQUEST
        headers = {'content-type': 'application/json'}
        r = requests.get(
            settings.elasticsearch.host+":"+str(settings.elasticsearch.port)+"/"+path,
            data=data,
            headers=headers,
            timeout=90
        )

        h=dict(r.headers)
        h["access-control-allow-origin"]="*"


        D.println("path: ${path}, request bytes=${request_content_length}, response bytes=${response_content_length}", {
            "path":path,
            "request_headers":dict(r.headers),
            "request_content_length":len(data),
            "response_headers":h,
            "response_content_length":len(r.content)
        })


        ## FORWARD RESPONSE
        return flask.wrappers.Response(
            r.content,
            status=r.status_code,
            headers=h
        )
    except Exception, e:
        D.warning("processing problem", e)
        abort(404)



## CALL abort(404) IF THIS IS NOT AN ElasticSearch QUERY
def filter(path, query):
    path=path.split("/")

    ## EXPECTING {index_name} "/" {type_name} "/_search"
    ## EXPECTING {index_name} "/_search"
    if len(path) not in [2, 3] or path[-1]!="_search": abort(404)

    ## EXPECTING THE QUERY TO AT LEAST LOOK LIKE A QUERY
    if CNV.JSON2object(query).query is None: abort(404)

    return True


# Snagged from http://stackoverflow.com/questions/10999990/python-flask-how-to-get-whole-raw-post-body
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
        app_iter = self.application(environ,
                                    self._sr_callback(start_response))

        # Return modified response
        return app_iter

    def _sr_callback(self, start_response):
        def callback(status, headers, exc_info=None):

            # Call upstream start_response
            start_response(status, headers, exc_info)
        return callback

app.wsgi_app = WSGICopyBody(app.wsgi_app)




if __name__ == '__main__':
    app.run(debug=settings.debug, port=settings.listen.port)
    app = HeaderRewriterFix(app, remove_headers=['Date', 'Server'])