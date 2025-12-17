#!/usr/bin/env python
import logging, logging.handlers
import sys, os
import argparse
import json
from types import SimpleNamespace
from urllib.parse import urlparse

from zabbix_api import ZabbixAPI
from zabbix_sender import ZabbixSender

import poplib
import email
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from email.utils import parseaddr
import ssl
import time

def main():
    # parse options
    parser = argparse.ArgumentParser(description='coming soon?')
    parser.add_argument('-z', '--zabbix', action='store', dest='zabbix', help='zabbix', default='http://localhost/zabbix/')
    parser.add_argument('--host', action='store', dest='host', help='host', default='localhost')
    parser.add_argument('-u', '--username', action='store', dest='username', help='username', default='Admin')
    parser.add_argument('-p', '--password', action='store', dest='password', help='password', default='zabbix')
    args = parser.parse_args()

    zabbix_url = args.zabbix
    if not zabbix_url.endswith('/'):
        zabbix_url = zabbix_url + '/'
    zabbix_url  = zabbix_url + 'api_jsonrpc.php'
    zabbix_host = urlparse(zabbix_url).hostname

    # logging
    log = logging.getLogger('zabbix-MT')
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s - %(message)s')

    here = os.path.abspath(os.path.dirname(__file__))
    logs = f'{here}/logs'
    if not os.path.exists(logs):
        os.mkdir(logs)

    # file
    rfh = logging.handlers.RotatingFileHandler(
        filename=f'{logs}/{args.host}.log',
        maxBytes=2000000, # MB
        backupCount=5
    )
    rfh.setFormatter(formatter)
    log.addHandler(rfh)

    # stdout
    stdout = logging.StreamHandler()
    stdout.setFormatter(formatter)
    log.addHandler(stdout)

    pop3 = None
    pop3_hostname = 'localhost'
    pop3_port     = 995
    pop3_username = 'username'
    pop3_password = 'password'

    try:
        print(json.dumps({'data': []}))

        # fork
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid > 0: # main process?
            sys.exit(0) # exit main process.

        # decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)

        # redirect standard file descriptors
        si = open('/dev/null', 'r')
        so = open('/dev/null', 'a+')
        se = open('/dev/null', 'a+')
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        log.info('starting application...')

        zabbix_api = ZabbixAPI(zabbix_url)
        zabbix_api.login(args.username, args.password)

        data = zabbix_api.get_host(host=args.host)
        #log.info(json.dumps(data, indent=2))

        host = SimpleNamespace(**data)

        for m in host.macros:
            if m['macro'] == '{$POP3_HOSTNAME}':
                pop3_hostname = m['value']
            elif m['macro'] == '{$POP3_PORT}':
                pop3_port = int(m['value'])
            elif m['macro'] == '{$POP3_USERNAME}':
                pop3_username = m['value']
            elif m['macro'] == '{$POP3_PASSWORD}':
                pop3_password = m['value']

        #log.info(pop3_hostname, pop3_username, pop3_password)

        if pop3_hostname is None and pop3_hostname == 'localhost':
            raise Exception('POP3 macro is not found on this host.')

        # zabbix sender
        sender = ZabbixSender(zabbix_host)

        log.info(f'connecting to pop3 server {pop3_hostname}...')

        # pop3 over ssl
        pop3 = poplib.POP3_SSL(pop3_hostname, pop3_port) # SSLポートは通常995
        log.info(pop3.getwelcome().decode())

        log.info(f'authenticating as user {pop3_username}...')

        pop3.user(pop3_username)
        pop3.pass_(pop3_password)

        messages = pop3.list()[1] # ['1 3706', '2 3674']
        num_messages = len(messages)

        log.info(f'total messages: {num_messages}')

        # mail message loop =>
        for i in range(1, num_messages + 1):
            try:
                resp, lines, octets = pop3.retr(i)
                raw = b'\n'.join(lines)
                msg = BytesParser(policy=policy.default).parsebytes(raw)
                subject = msg.get('Subject')
                from_name, from_addr = parseaddr(msg.get('From'))
                body = msg.get_body(preferencelist=('plain', 'html')).get_content()

                data = {
                        'date': msg.get('Date'),
                        'from': from_addr,
                        'subject': subject,
                        'body': body
                       }

                log.info(f'sending zabbix trapper message ({subject}) to {args.host}...')

                sender.set_packet(
                        host=args.host,
                        key='MAIL',
                        val=json.dumps(data, indent=2, ensure_ascii=False)
                        )

                res = sender.send()
            finally:
                pop3.dele(i)
        # <= mail message loop
    except Exception as e:
        log.error("Oops! Exception caught:", exc_info=True)
    finally:
       if pop3:
           log.info('quiting...')
           pop3.quit()

if __name__ == '__main__':
    main()
