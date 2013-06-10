
from flask import Flask
import flask
from flask.helpers import jsonify, make_response
import requests
import sys
from werkzeug.contrib.fixers import HeaderRewriterFix
from werkzeug.exceptions import abort
from util.cnv import CNV
from util.debug import D
from util.map import Map


app = Flask(__name__)


settings=Map(**{
    "host":"http://klahnakoski-es.corp.tor1.mozilla.com",
    "port":9200,
    "debug":"true"
})



@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    try:
        data = flask.request.environ['body_copy']
        filter(path, data)

        ## SEND REQUEST
        headers = {'content-type': 'application/json'}
        r = requests.get(
            settings.host+":"+str(settings.port)+"/"+path,
            data=data,
            headers=headers,
            timeout=90
        )

        ## WASSUP?!  r.headers SHOULD BE JSON, OR OBJECT, OR ITERABLE, OR SOMETHING?
        h=str(r.headers)[20:-1].replace("\"", "\\""").replace("'", "\"")
        h=dict([(k, v) for k, v in CNV.JSON2object(h).items()])
        h["access-control-allow-origin"]="*"

        D.println("path: ${path}", {"path":path, "request_body":data, "response_body":r.content})

        ## FORWARD RESPONSE
        return flask.wrappers.Response(
            r.content,
            status=r.status_code,
            headers=h
        )
    except Exception, e:
        D.warning("processing problem", e)




## CALL abort(404) IF THIS IS NOT AN ElasticSearch QUERY
def filter(path, query):
    path=path.split("/")

    ## EXPECTING {index_name} "/" {type_name} "/_search"
    ## EXPECTING {index_name} "/_search"
    if len(path) not in [2, 3] or path[-1]!="_search": abort(404)

    ## EXPECTING THE QUERY TO AT LEAST LOOK LIKE A QUERY
    if CNV.JSON2object(query).query is None: abort(404)

    return True



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
    app.run(debug=settings.debug)
    app = HeaderRewriterFix(app, remove_headers=['Date', 'Server'])