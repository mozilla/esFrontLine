################################################################################
## This Source Code Form is subject to the terms of the Mozilla Public
## License, v. 2.0. If a copy of the MPL was not distributed with this file,
## You can obtain one at http://mozilla.org/MPL/2.0/.
################################################################################
## Author: Kyle Lahnakoski (kyle@lahnakoski.com)
################################################################################
from string import Template
from test.test_zlib import zlib

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
        response = requests.get(
            settings.elasticsearch.host+":"+str(settings.elasticsearch.port)+"/"+path,
            data=data,
            stream=True, #FOR STREAMING
            headers=headers,
            timeout=90
        )

        stream = response.raw.stream(decode_content=False)

        # ALLOW CROSS DOMAIN (BECAUSE ES IS USUALLY NOT ON SAME SERVER AS PAGE)
        outbound_header=dict(response.headers)
        outbound_header["access-control-allow-origin"]="*"

        # RE-ZIP RESPONSE CONTENT (DOES NOT WORK)
#        content=response.content
##        if len(content)>1000:
##            h["content-encoding"]="gzip"
##            content=zlib.compress(content)
##        else:
##            h["content-encoding"]="text"
#        outbound_header["content-encoding"]="text"
#
#        outbound_header["content-length"]=str(len(content))


        D.println("path: {{path}}, request bytes=\{\{$1\}\}}, response bytes=\{\{$1\}\}} ({{response_content}}...)", {
            "path":path,
            "request_headers":dict(response.headers),
            "request_content_length":len(data),
            "response_headers":outbound_header,
            "response_content_length":outbound_header["content-length"],
            "response_content":response.content[0:100]
        })


        ## FORWARD RESPONSE
        return flask.wrappers.Response(
            response=stream,
#            response=content,   #content MUST BE A GENERATOR FOR STREAMING
            #response=response.iter_content(), #GENERATOR FOR STREAMING
            direct_passthrough=True, #FOR STREAMING
            status=response.status_code,
            headers=outbound_header
        )
    except Exception, e:
        D.warning("processing problem", e)
        abort(400)



## THROW EXCEPTION IF THIS IS NOT AN ElasticSearch QUERY
def filter(path, query):
    path=path.split("/")

    ## EXPECTING {index_name} "/" {type_name} "/_search"
    ## EXPECTING {index_name} "/_search"
    if len(path) not in [2, 3]:
        D.error("Not allowed")
    if path[-1] not in ["_mapping", "_search"]:
        D.error("Not allowed")

    ## EXPECTING THE QUERY TO AT LEAST HAVE .query ATTRIBUTE
    if path[-1]=="_search" and CNV.JSON2object(query).query is None:
        D.error("Not allowed")

    ## NO CONTENT ALLOWED WHEN ASKING FOR MAPPING
    if path[-1]=="_mapping" and len(query)>0:
        D.error("Not allowed")




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
    app.run(
        debug=(settings.debug is not None),
        host='0.0.0.0',
        port=settings.listen.port
    )
    app = HeaderRewriterFix(app, remove_headers=['Date', 'Server'])