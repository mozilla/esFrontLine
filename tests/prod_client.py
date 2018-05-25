import json

from elasticsearch import Elasticsearch

from esFrontLine.connection import HawkConnection
from mo_kwargs import override
from mo_logs import startup, constants, Log


@override
def main(elasticsearch, users, url_prefix, kwargs):
    Log.note('Will connect to esfrontline: {{url}}', url=elasticsearch)

    # Load users config
    user = users[0]
    Log.note('Will connect as {{user}}', user=user.hawk.id)

    # HawkConnection.url_prefix = url_prefix
    es = Elasticsearch(
        hosts=[elasticsearch],
        connection_class=HawkConnection,
        hawk_credentials=user.hawk,
        url_prefix=url_prefix
    )
    es.ping()

    index = user.resources[0]
    Log.note("Query {{index}}", index=index)
    Log.note('Count: {{result}}', result=es.count(index=index))
    response = es.search(index=user['resources'][0], body={"query": {"match_all": {}}, "size": 0})
    Log.note('Query:\n{{result}}', result=response)


if __name__ == '__main__':
    try:
        settings = startup.read_settings()
        constants.set(settings.constants)
        Log.start(settings.debug)

        main(settings)
    except Exception as e:
        Log.error("problem", cause=e)
    finally:
        Log.stop()