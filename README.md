esFrontLine
===========

Limit restful requests to backend ElasticSearch cluster:  Queries only.




Status (2013-Jun-10)
====================

This project is in development.  Please note the ```requirements.txt``` file is pointing
to the most recent version of pyLibrary, which could be unstable


Installation
============

I will assume you have python installed:

    git clone https://github.com/klahnakoski/esFrontLine.git

	cd esFrontLine

	pip install -r requirements.txt


Execution
=========

    python app.py --settings-file <path_to_file_with_JSON_settings>

The settings file is a flexible JSON file with the following values set:

  * **elasticsearch.host** - url of the elastic search cluster where requests will
   be forwarded to

  * **elasticsearch.port** - port for ES (default = 9200)

  * **listen.port** - is the port that this application will listen on (default 5000)

  * **debug** - turn on debugging