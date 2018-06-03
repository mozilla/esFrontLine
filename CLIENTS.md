Elasticsearch clients
=====================

This tool is compatible with official Python Elasticsearch clients:

* [elasticsearch-py](https://elasticsearch-py.readthedocs.io/en/master/)
* [elasticsearch-py-async](https://github.com/elastic/elasticsearch-py-async)

In order to use the HAWK authentication, you will need 4 informations:

1. the **esFrontLine** full url
2. the user credentials ID
3. the user credentials secret (or password), named `key`
4. the user credentials digest algorithm (by default `sha256`)

In the code samples below, we'll use these variables:

```python
url = 'http://frontline.example.com/prefix'
user = {
  'id': 'USER_ID',
  'key': 'USER_SECRET',
  'algorithm': 'sha256',
}
```

Synchronous client
------------------

In most cases you will need to use a synchronous client such as `elasticsearch-py`.

Here is a code sample showing how to use **esFrontLine** authentication:

```python
from elasticsearch import Elasticsearch
from esFrontLine.client import HawkConnection

es = Elasticsearch(
    hosts=[url, ],
    connection_class=HawkConnection,
    hawk_credentials=user,
)

assert es.ping()
```

Asynchronous client
------------------

You can also use our client with asynchronous code:

```python
import asyncio
from elasticsearch_async import AsyncElasticsearch
from esFrontLine.client.async import AsyncHawkConnection

es = AsyncElasticsearch(
    hosts=[url, ],
    connection_class=AsyncHawkConnection,
    hawk_credentials=user,
)

async def async_ping():
    p = await es.ping()
    print('ping', p)

loop = asyncio.get_event_loop()
loop.run_until_complete(async_ping())
loop.close()
```
