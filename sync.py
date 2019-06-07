#!/usr/bin/env python3

import json
import urllib

from enum import IntEnum
from http.client import HTTPResponse
from settings import *
from typing import List, Set, Dict, Optional
from urllib.parse import urlencode, urlunparse, ParseResult
from urllib.request import urlopen

class ListType(IntEnum):
    WHITELIST = 1
    BLACKLIST_EXACT = 2
    BLACKLIST_REGEX = 3

    def name(self) -> str:
        if self.value == self.WHITELIST:
            return "whitelist"
        if self.value == self.BLACKLIST_EXACT:
            return "blacklist (exact)"
        return "blacklist (regex)"

class Host:
    address: str
    webpassword: str
    _list_cache: Dict[ListType, List[str]]

    def __init__(self, address: str, webpassword: str):
        self.address = address
        self.webpassword = webpassword
        self._list_cache = {}

    def __str__(self):
        return self.address

    def _api_call(self, query_params={}, auth=False) -> HTTPResponse:
        """
        Makes a call to the PHP API (/admin/api.php) with the specified query
        params. If auth is True, the call is authenticated with the host's
        webpassword.
        """
        if auth:
            query_params['auth'] = self.webpassword
        components = ParseResult(
            scheme = 'http',
            netloc = self.address,
            path = '/admin/api.php',
            params = '',
            query = urlencode(query_params),
            fragment = ''
        )
        url = urlunparse(components)
        return urlopen(url)

    def get_list(self, list_type: ListType) -> List[str]:
        """
        Gets the list of domains of the specified type and returns it
        """
        try:
            return self._list_cache[list_type]
        except KeyError:
            list_api_arg = "black"
            if list_type == ListType.WHITELIST:
                list_api_arg = "white"
            response = self._api_call({"list": list_api_arg}, auth=True)

            # Parse the results
            results = json.loads(response.read())

            # Cache the results
            if list_type == ListType.WHITELIST:
                self._list_cache[ListType.WHITELIST] = results[0]
            else:
                # Calling the API with list=black returns both blacklists in the
                # same response. Cache both to save us another round trip later.
                self._list_cache[ListType.BLACKLIST_EXACT] = results[0]
                self._list_cache[ListType.BLACKLIST_REGEX] = results[1]

            return self._list_cache[list_type]

    def add_list_entry(self, entry: str, list_type: ListType):
        """
        Adds an entry to the list of the specified type.
        """
        # Invalidate the cache
        try:
            del self._list_cache[list_type]
        except KeyError:
            pass

        print("+ Adding {} to {} on {}".format(
            entry,
            list_type.name(),
            self.address
        ))

        # NB: when fetching lists, the list arg is 'black' or 'white', and
        # 'black' returns the exact and regex blacklists in one result. But when
        # setting lists, the list arg is 'black', 'white' or 'regex' (or a
        # couple of others we don't use). See
        # https://github.com/pi-hole/AdminLTE/blob/master/scripts/pi-hole/php/add.php
        list_api_arg: str
        if list_type == ListType.WHITELIST:
            list_api_arg = "white"
        elif list_type == ListType.BLACKLIST_EXACT:
            list_api_arg = "black"
        else:
            list_api_arg = "regex"
        self._api_call({ "list": list_api_arg, "add": entry }, auth=True)

def load_hosts_from_config() -> Set[Host]:
    """
    Gets a set of Host objects based on the config in settings.py
    """
    hosts = []
    for hc in HOST_CONFIGS:
        hosts.append(Host(hc["address"], hc["webpassword"]))
    return set(hosts)

def _sync_list(hosts: Set[Host], list_type: ListType) -> int:
    """
    Syncs the list of the specified type between all hosts. All hosts will end
    up with the union of all lists of this type.

    For example: in the scenario where you have two hosts which have the
    following whitelists:

    Host 1: ["foo.com", "bar.com"]
    Host 2: ["bar.com", "wibble.com"]

    After running `_sync_hosts` with `list_type: ListType.WHITELIST`, both hosts
    will have the following whitelist:

    ["foo.com", "bar.com", "wibble.com"]
    """
    sync_count = 0

    # First, build a dictionary mapping entries to a set of all the host(s) that
    # already have that entry in the appropriate list.
    entries_per_host: Dict[str, Set[Host]] = {}
    for host in hosts:
        lst = host.get_list(list_type)
        for entry in lst:
            try:
                entries_per_host[entry].add(host)
            except KeyError:
                entries_per_host[entry] = set([host])

    # Now step through all the entries we found, adding them to any hosts that
    # don't already have them.
    for entry in entries_per_host:
        # Get the hosts who already have this entry
        hosts_with_entry = entries_per_host[entry]
        if len(hosts_with_entry) == len(hosts):
            # All hosts have this entry: nothing to do
            continue
        sync_count += 1

        # The hosts without the entry is the set of all hosts minus the set of
        # hosts that do have the entry.
        hosts_without_entry = hosts - hosts_with_entry

        # For each of those hosts, go ahead and add the entry
        for h in hosts_without_entry:
            h.add_list_entry(entry, list_type)
    return sync_count

def sync_lists(hosts: Set[Host]):
    """
    Calls _sync_list for each list type. See that function for a discussion of
    the logic involved.
    """
    for list_type in ListType:
        sync_count = _sync_list(hosts, list_type)
        print("{}: {} item(s) synced between hosts".format(
            list_type.name(),
            sync_count
        ))

if __name__ == "__main__":
    hosts = load_hosts_from_config()

    sync_lists(hosts)
