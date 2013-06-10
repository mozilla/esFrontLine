#!flask/bin/python
from flask import Flask
import flask
from flask.helpers import jsonify, make_response
import requests
from werkzeug.exceptions import abort

app = Flask(__name__)


settings={
    "host":"http://klahnakoski-es.corp.tor1.mozilla.com"
}


if __name__ == '__main__':
    app.run(debug = True)



#@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    data = flask.request.data
    data = ''.join(flask.request.environ['wsgi.input'].readlines())

    filter(path, data)

    ## SEND REQUEST
    headers = {'content-type': 'application/json'}
    r = requests.get(settings["host"]+path, data=data, stream=True, headers=headers)

    ## FORWARD RESPONSE
    return flask.wrappers.Response(r.raw, status=r.status_code, headers=r.headers)



@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify( { 'error': 'Only queries allowed' } ), 404)



## CALL abort(404) IF THIS IS NOT AN ElasticSearch QUERY
def filter(path, query):
    path=path.split("/")

    ## EXPECTING {index_name} "/" {type_name} "/_search"
    ## EXPECTING {index_name} "/_search"
    if len(path) not in [2, 3] or path[-1]!="_search": abort(404)

    ## EXPECTING THE QUERY TO AT LEAST LOOK LIKE A QUERY
    if "query" not in jsonify(query): abort(404)

    return True