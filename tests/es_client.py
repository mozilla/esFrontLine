import json
import argparse
import elasticsearch
from esFrontLine.connection import HawkConnection


def main(settings):

    # Load flask config
    flask = settings.get('flask')
    assert flask and 'host' in flask and 'port' in flask, \
        'Invalid flask settings'
    server_url = 'http://{host}:{port}'.format(**flask)
    print('Will connect to esfrontline: {}'.format(server_url))

    # Load users config
    users = settings.get('users')
    assert users, 'Missing users in settings'
    user = users[0]
    assert 'hawk' in user, 'Missing hawk conf in first user'
    assert 'resources' in user, 'Missing resources in first user'
    print('Will connect as {}'.format(user['hawk']['id']))

    es = elasticsearch.Elasticsearch(
        hosts=[server_url],
        connection_class=HawkConnection,
        hawk_credentials=user['hawk'],
    )
    es.ping()
    print('Count: {}'.format(es.count(index=user['resources'][0])))
    response = es.search(index=user['resources'][0], body={'query': {}})
    print('Response:\n{}'.format(json.dumps(response, sort_keys=True, indent=4)))

if __name__ == '__main__':

    # Load server settings to automatically create a dev client
    parser = argparse.ArgumentParser()
    parser.add_argument(
        help='Path to JSON file with settings',
        type=open,
        dest='settings',
    )
    args = parser.parse_args()

    main(json.load(args.settings))

