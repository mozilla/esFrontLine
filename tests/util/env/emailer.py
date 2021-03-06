# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#

from __future__ import unicode_literals
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import sys
from .. import struct
from ..struct import nvl


class Emailer:
    def __init__(self, settings):
        """
        REQUIRES SETTINGS LIKE
        "email": {
            "from_address": "klahnakoski@mozilla.com",  #DEFAULT
            "to":"klahnakoski@mozilla.com",  #DEFAULT
            "subject": "catchy title",  #DEFAULT
            "host": "mail.mozilla.com",
            "port": 465,
            "username": "example@example.com",
            "password": "password",
            "use_ssl": 1
        }
        """
        self.settings = settings


    def send_email(self,
            from_address=None,
            to_addrs=None,
            subject=None,
            text_data=None,
            html_data=None
    ):
        """Sends an email.

        from_addr is an email address; to_addrs is a list of email adresses.
        Addresses can be plain (e.g. "jsmith@example.com") or with real names
        (e.g. "John Smith <jsmith@example.com>").

        text_data and html_data are both strings.  You can specify one or both.
        If you specify both, the email will be sent as a MIME multipart
        alternative, i.e., the recipient will see the HTML content if his
        viewer supports it; otherwise he'll see the text content.
        """

        settings = self.settings

        from_address = nvl(from_address, settings["from"], settings.from_address)
        to_addrs = listwrap(nvl(to_addrs, settings.to, settings.to_addrs))

        if not from_address or not to_addrs:
            raise Exception("Both from_addr and to_addrs must be specified")
        if not text_data and not html_data:
            raise Exception("Must specify either text_data or html_data")

        if settings.use_ssl:
            server = smtplib.SMTP_SSL(settings.host, settings.port)
        else:
            server = smtplib.SMTP(settings.host, settings.port)

        if settings.username and settings.password:
            server.login(settings.username, settings.password)

        if not html_data:
            msg = MIMEText(text_data)
        elif not text_data:
            msg = MIMEMultipart()
            msg.preamble = nvl(subject, settings.subject, 'No Subject')
            msg.attach(MIMEText(html_data, 'html'))
        else:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(text_data, 'plain'))
            msg.attach(MIMEText(html_data, 'html'))

        msg['Subject'] = nvl(subject, settings.subject)
        msg['From'] = from_address
        msg['To'] = ', '.join(to_addrs)

        server.sendmail(from_address, to_addrs, msg.as_string())

        server.quit()


if sys.hexversion < 0x020603f0:
    # versions earlier than 2.6.3 have a bug in smtplib when sending over SSL:
    #     http://bugs.python.org/issue4066

    # Unfortunately the stock version of Python in Snow Leopard is 2.6.1, so
    # we patch it here to avoid having to install an updated Python version.
    import socket
    import ssl

    def _get_socket_fixed(self, host, port, timeout):
        if self.debuglevel > 0:
            print>> sys.stderr, 'connect:', (host, port)
        new_socket = socket.create_connection((host, port), timeout)
        new_socket = ssl.wrap_socket(new_socket, self.keyfile, self.certfile)
        self.file = smtplib.SSLFakeFile(new_socket)
        return new_socket

    smtplib.SMTP_SSL._get_socket = _get_socket_fixed


