from mohawk import Sender
import requests
import json
import argparse


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

    # Build content to send (ES Query)
    content = json.dumps({
        'query': {},
    })

    # Build full url
    url = '{}/{}/test/_search'.format(server_url, user['resources'][0])

    # Build Hawk header
    sender = Sender(user['hawk'], url, 'GET', content, content_type='application/json')
    print('Hawk header: {}'.format(sender.request_header))

    # Send request to server
    headers = {
        'Content-Type': 'application/json',
        'Authorization': sender.request_header,
    }
    response = requests.get(url, data=content, headers=headers)
    response.raise_for_status()
    print('Response:\n{}'.format(json.dumps(response.json(), sort_keys=True, indent=4)))

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
