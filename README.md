esFrontLine
===========

Limit restful requests to backend ElasticSearch cluster:  Queries only.


Requirements
------------

  * Python 2.7
  * An ElasticSearch cluster to forward queries to


Install
------------

I will assume you have Python installed (if not, here are [Windows7 instructions](https://github.com/klahnakoski/pyLibrary#windows-7-install-instructions-))

    git clone https://github.com/klahnakoski/esFrontLine.git

    cd esFrontLine

	pip install -r requirements.txt

Setup
-----

You must right your own setting.jason file with the following properties set:

  * **elasticsearch** - (Array of) ElasticSearch host pointers

  * **elasticsearch.host** - URL of the ElasticSearch cluster that will accept query requests

  * **elasticsearch.port** - port for ES (default = 9200)

  * **listen.port** - The port that this application will listen on (default 5000)

  * **flask** - flask.run() parameters

  * **debug** - turn on debugging

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
        "debug":{
            "log":[{
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "./results/logs/app.log",
                "maxBytes": 10000000,
                "backupCount": 200,
                "encoding": "utf8"
            },{
                "class":"esFrontLine.util.logs.Log_usingStream",
                "stream":"sys.stdout"
            }]
        }

    }
Execution
---------

    python app.py --settings-file <path_to_file_with_JSON_settings>

