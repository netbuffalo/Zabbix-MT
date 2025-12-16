import json
import urllib.request, urllib.parse, urllib.error
import os
import time

class ZabbixAPIException (Exception):
    pass

class ZabbixAPI(object):

    def __init__(self,
            url: str        = None,
            host: str       = None,
            port: int       = 80,
            request_id: int = 1,
            jsonrpc: str    = '2.0',
            ):

        self.host = host
        self.port = port

        self.username = 'Admin'
        self.password = 'zabbix'

        self.url = None
        if url is None and host is None:
            self.url = 'http://localhost/zabbix/api_jsonrpc.php'
        else:
            if host is not None:
                self.url = f'http://{host}:{port}/zabbix/api_jsonrpc.php'

            if url is not None:
                if   url.endswith('/api_jsonrpc.php'):
                    self.url = url
                elif url.endswith('/'):
                    self.url = url + 'api_jsonrpc.php'
                else:
                    self.url = url + '/api_jsonrpc.php'

        self.request_id = request_id
        self.jsonrpc = jsonrpc

        #self.token = None
        self.zbx_sessionid = None
        self.key_zbx_sessionid = None

    def login(self, username: str = 'Admin', password: str = 'zabbix'):
        self.username = username
        self.password = password


        # get new session id from zabbix =>
        # get api version.
        params = {
            'jsonrpc': self.jsonrpc,
            'method': 'apiinfo.version',
            'id': self.request_id,
            'params': []
        }

        response = self.do_zabbix_api(params)

        zabbix_version = 0
        if response and 'result' in response:
            zabbix_version = int(response['result'].split('.')[0])
        else:
            raise ZabbixAPIException("Authentication error occurred!")

        if zabbix_version > 5:
            auth = {'username': username, 'password': password}
        else: # version <= 5.x
            auth = {'user': username, 'password': password}

        auth['userData'] = True

        # login
        params = {
            'jsonrpc': self.jsonrpc,
            'method': 'user.login',
            'id': self.request_id,
            'params': auth
        }

        response = self.do_zabbix_api(params)

        if response and 'result' in response:
            self.zbx_sessionid = response['result']['sessionid']
            return self
        else:
            raise ZabbixAPIException("Authentication error occurred by %s!" % username)

    def logout(self):
        if self.zbx_sessionid is not None:
            payload = {
                'jsonrpc': self.jsonrpc,
                'method': 'user.logout',
                'id': self.request_id,
                'params': [],
                'auth': self.zbx_sessionid
            }

            response = self.do_zabbix_api(payload)

            if response and 'result' in response:
                # delete session id from redis.
                redis = Redis.StrictRedis(
                        host=self.redis_host, port=self.redis_port,
                        db=self.redis_db, password=self.redis_password)
                # delete
                redis.delete(self.key_zbx_sessionid)
                self.zbx_sessionid =  None
                return response['result']
            else:
                raise ZabbixAPIException("Authentication error occurred.")

    def do_zabbix_api(self, json_request):
        json_response = {}
        headers = {'Content-Type': 'application/json'}
        data = json.dumps(json_request).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method='POST', headers=headers)
        with urllib.request.urlopen(req, timeout=300) as res:
            if res.getcode() == 200: # is http status ok (200) ?
                data = json.loads(res.read())
                if 'error' in data:
                    if 'session terminated' in data['error']['data'].lower():
                        # initialize sessionid cache.
                        # delete session id from redis.
                        redis = Redis.StrictRedis(
                                host=self.redis_host, port=self.redis_port,
                                db=self.redis_db, password=self.redis_password)

                        redis.delete(self.key_zbx_sessionid)
                        self.zbx_sessionid =  None
                        raise ZabbixAPIException(data['error']['data'])
                    else:
                        raise ZabbixAPIException(data['error']['data'])
                else:
                    json_response = data
            else:
                raise ZabbixAPIException("HTTP status code is not success (%d)!" % res.getcode())

        return json_response

    def request(self, **args):
        response = {}
        max_retries = 3
        cur_retries = 0
        auth        = args['auth'] if 'auth' in args else True
        while cur_retries < max_retries:
            try:
                if auth and self.zbx_sessionid is None:
                    self.login(self.username, self.password)

                req = {
                    'jsonrpc': self.jsonrpc,
                    'method': args['method'],
                    'id': self.request_id,
                    'params': args['params']
                }

                if auth:
                    req['auth'] = self.zbx_sessionid

                response = self.do_zabbix_api(req)
                break # break retry loop.
            except ZabbixAPIException as e:
#                traceback.print_exc()
                cur_retries += 1
                time.sleep(cur_retries * 3)

        if 'result' in response:
            return response['result']
        else:
            raise ZabbixAPIException("Zabbix API request failed. %s" % response)

    def get_api_version(self):
        response = self.request(method='apiinfo.version', params={})
        return response

    def __enter__(self):
        if self.zbx_sessionid is None:
            self.login()
        return self

    def __exit__(self, type, value, traceback):
        #self.logout()
        pass

    def __get_hosts_by_host(self, host: str):
        params = {
                'output': ['host', 'name', 'description', 'status'],
                'search': {
                    'host': host
                    },
                'searchWildcardsEnabled': True
                }

        res = self.request(method='host.get', params=params)

        for r in res:
            r['hostid'] = int(r['hostid'])
            r['status'] = True if int(r['status']) == 0 else False

        return res

    def __get_host_by_host(self, host: str):
        hosts = self.__get_hosts_by_host(host)
        for h in hosts:
            if h['host'] == host:
                return h

    def __get_host_by_hostid(self, hostid: int):
        params = {
                'hostids': hostid,
                'output': ['host', 'name', 'description', 'status']
                }

        hosts = self.request(method='host.get', params=params)

        for h in hosts:
            h['hostid'] = int(h['hostid'])
            h['status'] = True if int(h['status']) == 0 else False
            return h

    def get_host(self, **kwargs: str):
        host = None

        if 'hostid' in kwargs:
            host = self.__get_host_by_hostid(hostid=kwargs['hostid'])
        elif 'host' in kwargs:
            host = self.__get_host_by_host(kwargs['host'])
        else:
            raise ValueError('Invalid args.')

        if host is None:
            return

        hostid = host['hostid']

        # get host macros.
        macros = self.__get_macros_by_hostid(hostid)

        # get host interfaces.
        interfaces = self.__get_interface_by_hostid(hostid)

        for i in interfaces:
            if 'details' in i and 'community' in i['details']:
                if i['details']['community'] not in ['', '{$SNMP_COMMUNITY}']:
                    community = i['details']['community']
                    has_community_macro = False
                    for m in macros:
                        if m['macro'] == '{$SNMP_COMMUNITY}':
                            m['value'] = community
                            has_community_macro = True
                            break
                    if not has_community_macro:
                        macros.append({'macro': '{$SNMP_COMMUNITY}', 'value': community})

        # set macros.
        host['macros'] = macros

        # set interfaces.
        host['interfaces'] = interfaces

        return host

    def __get_macros_by_hostid(self, hostid: int):
        macros = {}

        # get grobalmacro ->
        params = {
                'output': ['macro', 'value'],
                'globalmacro': True,
                'hostids': hostid
                }

        res = self.request(method='usermacro.get', params=params)

        for m in res:
            macros[m['macro']] = m['value']

        # <- get globalmacro

        # get parent template macros ->
        params = {
                'hostids': hostid,
                'output': ['hostid'],
                'selectParentTemplates':['templateid', 'host'],
                }

        res = self.request(method='host.get', params=params)

        p_templates = res.pop(0)['parentTemplates']

        for pt in p_templates:
            templateid = pt['templateid']
            params = {
                    'hostids': templateid,
                    'output':  ['macro', 'value']
                    }

            for m in self.request(method='usermacro.get', params=params): # template loop.
                macros[m['macro']] = m['value']
        # <- get parent template macros

        # get host macros ->
        params = {
                'hostids': hostid,
                'output':  ['macro', 'value']
                }

        res = self.request(method='usermacro.get', params=params)

        for m in res:
            macros[m['macro']] = m['value']
        # <- get host macros

        # convert dict to list (in dict).
        macros = [{'macro': m, 'value': v} for m, v in macros.items()]

        return macros

    def __get_interface_by_hostid(self, hostid: int):
        interfaces = []

        params = {
                'hostids': hostid,
                'output':  'extend'
                }

        res = self.request(method='hostinterface.get', params=params)

        for f in res:
            iface = {
                        'interfaceid': int(f['interfaceid']),
                        'main': int(f['main']),
                        'type': int(f['type']),
                        'useip': int(f['useip']),
                        'ip': f['ip'],
                        'dns': f['dns']
                    }

            if 'details' in f and len(f['details']) > 0:
                iface['details'] = f['details']

            interfaces.append(iface)

        return interfaces

