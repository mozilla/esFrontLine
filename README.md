esFrontLine
===========

Limit restful requests to backend ElasticSearch cluster:  Queries for the public, 


Requirements
------------

  * Python 2.7 or 3.6.2+
  * An ElasticSearch cluster to forward queries to


Install
------------

I will assume you have Python installed (if not, here are [Windows7 instructions](https://github.com/klahnakoski/pyLibrary#windows-7-install-instructions-))

    pip install esFrontLine

Setup
-----

You must write your own setting.json file with the following properties set:

  * **elasticsearch** - (Array of) ElasticSearch nodes
  * **elasticsearch.host** - URL of the ElasticSearch node that will accept query requests
  * **elasticsearch.port** - port for ES (default = 9200)
  * **flask** - flask.run() parameters (default port = 5000)
  * **whitelist** - list of indexes that are allowed
  * **users** - list of allowed HAWK users, with their linked resources
  * **users.resources** - list of indexes the user is allowed
  * **users.hawk** - object of [Hawk credentials](https://github.com/hueniverse/hawk/blob/master/README.md)
  * **users.hawk.id** - any human readable name to identify the user or application
  * **users.hawk.key** - the secret value held by both endpoints and not shared with anyone
  * **users.hawk.algorithm**: always "sha256" for now
  * **debug** - for debugging

Here is an example of my ```settings.json``` file

    {
        "elasticsearch":[{
            "host":"http://elasticsearch4.metrics.scl3.mozilla.com",
            "port":9200
        },{
            "host":"http://elasticsearch5.metrics.scl3.mozilla.com",
            "port":9200
        },{
            "host":"http://elasticsearch7.metrics.scl3.mozilla.com",
            "port":9200
        },{
            "host":"http://elasticsearch8.metrics.scl3.mozilla.com",
            "port":9200
        }],
        "flask":{
            "host":"0.0.0.0",
            "port":9292,
            "debug":false,
            "threaded":true,
            "processes":1
        },
        "users": [
          {
            "hawk": {
              "id": "kyle@example.com",
              "key": "secret",
              "algorithm": "sha256"
            },
            "resources": [
              "testing"
            ]
          }
        ],
        "whitelist":["bugs", "org_chart", "bug_summary", "reviews"],
        "debug":{
            "log":[{
                "filename": "./tests/results/logs/app.log",
                "maxBytes": 10000000,
                "backupCount": 200,
                "encoding": "utf8"
            },{
                "stream":"sys.stdout"
            }]
        }

    }

Execution
---------

    python app.py --settings-file <path_to_file_with_JSON_settings>

Code Source
-----------

[https://github.com/klahnakoski/esFrontLine](https://github.com/klahnakoski/esFrontLine)
