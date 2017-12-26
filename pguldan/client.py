import os
import json
import urlparse
import threading
import requests
import time
from collections import deque
import version

class Item:
    def __init__(self, org, proj, name, value, token, version, gray, timeout):
        self._org = org
        self._proj = proj
        self._name = name
        self._value = value
        self._token = token
        self._version = version
        self._gray = gray
        self._timeout = time.time() + timeout
    def __str__(self):
        t = {}
        t['org'] = self._org
        t['proj'] = self._proj
        t['name'] = self._name
        t['value'] = self._value
        t['token'] = self._token
        t['version'] = self._version
        t['gray'] = self._gray
        t['timeout'] = self._timeout
        return json.dumps(t)

    __repr__ = __str__

    def rid(self):
        return self._org + "." + self._proj + "." + self._name
    def org(self):
        return self._org
    def proj(self):
        return self._proj
    def name(self):
        return self._name
    def token(self):
        return self._token
    def version(self):
        return self._version
    def value(self):
        return self._value
    def gray(self):
        return self._gray
    def timeout(self):
        return self._timeout
    def set_expired(self, timeout):
        self._timeout = timeout
    def expired(self):
        return self._timeout <= time.time()

class Cache:
    def __init__(self, async=False):
        self._cache = {}
        self._timeouts = []
        self._lock = threading.Lock()
        self._async = async
    def get(self, key):
        with self._lock:
            if self._cache.has_key(key):
                return self._cache[key]
            return None
    def set(self, key, item):
        with self._lock:
            self._cache[key] = item
            if self._async:
                self._timeouts.append((key, item.timeout()))
    def remove(self, key):
        with self._lock:
            if self._cache.has_key(key):
                del self._cache[key]
    def refresh(self, key, timeout):
        expired = time.time() + timeout
        with self._lock:
            if self._cache.has_key(key):
                self._cache[key].set_expired(expired)
            if self._async:
                self._timeouts.append((key, expired))
    def get_update_items(self):
        t = []
        with self._lock:
            t.extend(self._timeouts)
            self._timeouts = []
        return t

def gen_cache_id(rid, token, gray):
    if token != None:
        rid = rid + ":" + token
    if gray:
        rid = rid + ":true"
    return rid

class Result(object):
    def __init__(self, code=-1, version="-1", content=None):
        self._code    = code
        self._version = version
        self._content = content

    def __str__(self):
        t = {}
        t['code']    = self._code
        t['version'] = self._version
        t['content'] = self._content
        return json.dumps(t)

    __repr__ = __str__

    def set_code(self, code):
        self._code = code
    def set_version(self, version):
        self._version = version
    def set_content(self, content):
        self._content = content

    def ok(self):
        return self._code == 200

    def code(self):
        return self._code

    def version(self):
        return self._version

    def content(self):
        return self._content

class Client(object):
    __instance_lock      = threading.Lock()
    __instance           = None

    def __init__(self, address, timeout=1, auto_refresh=False, refresh_interval=10):
        self._callbacks = {}
        self._callbacks_lock = threading.Lock()
        self._address = address
        if not self._address.endswith("/"):
            self._address = self._address + "/api/puller/"
        else:
            self._address = self._address + "api/puller/"
        self._timeout = timeout
        self._cache = Cache(auto_refresh)
        self._role = "client"
        self._refresh_interval = refresh_interval
        self._auto_refresh = auto_refresh
        self._printer = None
        if auto_refresh:
            background = threading.Thread(target=self._bgwork)
            background.setName("guldan-bg")
            background.setDaemon(True)
            self._background = background
            background.start()

    @classmethod
    def instance(cls, address, timeout=1, auto_refresh=False):
        if not cls.__instance:
            with cls.__instance_lock:
                if not cls.__instance:
                    cls.__instance = cls(address, timeout, auto_refresh)
        return cls.__instance

    def _get_callback(self, cache_id):
        with self._callbacks_lock:
            if self._callbacks.has_key(cache_id):
                return self._callbacks[cache_id]
        return None

    def subscribe(self, rid, callback, token=None, gray=False):
        with self._callbacks_lock:
            self._callbacks[gen_cache_id(rid, token, gray)] = callback

    def _bgwork(self):
        while True:
            time.sleep(self._refresh_interval)
            expires = self._cache.get_update_items()
            if len(expires) > 0:
                idx = 0
                while idx < len(expires):
                    while idx < len(expires):
                        expire = expires[idx]
                        if expire[1] > time.time():
                            break
                        cache_id = expire[0]
                        local_item = self._cache.get(cache_id)
                        if local_item == None:
                            idx = idx + 1
                            continue
                        result = self._get_config_from_remote(local_item.org(), local_item.proj(),
                            local_item.name(), local_item.token(), local_item.version(), local_item.gray())
                        code = result.code()
                        if code == 200:
                            if local_item == None or local_item.version() != result.version():
                                if self._try_do_callback(cache_id, result):
                                    item = Item(local_item.org(), local_item.proj(), local_item.name(),
                                            result.content(), local_item.token(), result.version(), local_item.gray(), self._refresh_interval)
                                    self._cache.set(cache_id, item)
                            else:
                                self._cache.refresh(cache_id, self._refresh_interval)
                        elif code == 404 or code == 403:
                            if self._try_do_callback(cache_id, result):
                                self._cache.remove(cache_id)
                        else:
                            self._cache.refresh(cache_id, self._refresh_interval)
                        idx = idx + 1
                    time.sleep(self._refresh_interval)

    def _try_do_callback(self, cache_id, result):
        callback = self._get_callback(cache_id)
        if callback != None and callback(cache_id, result) == False:
            self._cache.refresh(cache_id, self._refresh_interval)
            return False
        return True

    def _get_config_from_remote(self, org, proj, name, token, local_version, gray):
        result = Result()
        payload = {}
        payload["grey"] = gray
        payload["cver"] = "python"+version.__version__
        payload["ctype"] = self._role
        payload["lver"] = local_version
        payload["cid"] = os.getpid()
        headers = None
        if token != None:
            headers = {"X-Guldan-Token": token}
        try:
            address = self._address + org + "/" + proj + "/" + name
            r = requests.get(address, params=payload, timeout=self._timeout, headers=headers)
            if r.status_code == requests.codes.ok:
                result.set_code(r.status_code)
                result.set_version(r.headers["X-Guldan-Version"])
                result.set_content(r.text)
            elif r.status_code == 404 or r.status_code == 403:
                result.set_code(r.status_code)
            else:
                if self._printer:
                    self._printer("request %s got error code %d" % (address, r.status_code))
        except Exception, e:
            if self._printer:
                self._printer("request %s got error %s" % str(e))
        return result

    def get_config(self, rid, token=None, gray=False):
        slices = None
        try:
            slices = rid.split(".")
            if len(slices) != 3:
                raise ValueError("rid:" + rid + " is invalid format")
        except AttributeError:
            raise ValueError("rid is invalid type")
        cache_id = gen_cache_id(rid, token, gray)
        local_item = self._cache.get(cache_id)
        if local_item != None and (self._auto_refresh or local_item.expired() == False):
            return Result(200, local_item.version(), local_item.value())
        v = "-1"
        if local_item != None:
            v = local_item.version()
        result = self._get_config_from_remote(slices[0], slices[1], slices[2], token, v, gray)
        code = result.code()
        if code == 200:
            if local_item == None or local_item.version() != result.version():
                item = Item(slices[0], slices[1], slices[2], result.content(), token, result.version(), gray, self._refresh_interval)
                self._cache.set(cache_id, item)
            else:
                self._cache.refresh(cache_id, self._refresh_interval)
        elif code == 404 or code == 403:
            self._cache.remove(cache_id)
        return result

