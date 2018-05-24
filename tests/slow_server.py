# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
from __future__ import division
from __future__ import unicode_literals

from flask import Flask, Response, abort
from mo_logs import startup, constants, Log

from mo_logs.strings import unicode2utf8, expand_template
from mo_threads import Till

SLOW_PORT = 9299
RATE = 4.0  # per second

app = Flask(__name__)


@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve_slowly(path):
    def octoberfest():
        for bb in range(99, 2, -1):
            Log.note("emit {{i}}", i=bb)
            yield (b"0" * 65535) + b"\n"  # ENOUGH TO FILL THE INCOMING BUFFER
            Till(seconds=1.0 / RATE).wait()
            yield unicode2utf8(expand_template("{{num}} bottles of beer on the wall! {{num}} bottles of beer!  Take one down, pass it around! {{less}} bottles of beer on the wall!\n", {
                "num": bb,
                "less": bb - 1
            }))
        yield (b"0" * 65535) + b"\n"  # ENOUGH TO FILL THE INCOMING BUFFER
        yield unicode2utf8(u"2 bottles of beer on the wall! 2 bottles of beer!  Take one down, pass it around! 1 bottle of beer on the wall!\n")
        yield (b"0" * 65535) + b"\n"  # ENOUGH TO FILL THE INCOMING BUFFER
        yield unicode2utf8(u"1 bottle of beer on the wall! 1 bottle of beer!  Take one down, pass it around! 0 bottles of beer on the wall.\n")

    try:
        # FORWARD RESPONSE
        return Response(
            octoberfest(),
            direct_passthrough=True,  # FOR STREAMING
            status=200
        )
    except Exception as e:
        abort(400)


if __name__ == "__main__":
    settings = startup.read_settings(filename="tests/config/slow_server.json")

    app.run(
        host="0.0.0.0",
        port=settings.elasticsearch.port,
        debug=False,
        threaded=False,
        processes=1
    )
    app.run(**settings.flask)
