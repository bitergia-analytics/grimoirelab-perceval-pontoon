#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Jose Javier Merchante <jjmerchante@bitergia.com>
#

import datetime
import json
import os
import unittest.mock

import httpretty
from dateutil.tz import tzutc

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.pontoon.pontoon import (Pontoon,
                                               PontoonCommand,
                                               PontoonClient)

PONTOON_ENTITIES = 'data/pontoon/pontoon_entities.json'
PONTOON_PAGE_1 = 'data/pontoon/pontoon_entities_page_1.json'
PONTOON_PAGE_2 = 'data/pontoon/pontoon_entities_page_2.json'
PONTOON_HISTORY = 'data/pontoon/pontoon_history.json'
PONTOON_LOCALES = 'data/pontoon/pontoon_locales.json'

PONTOON_URL = 'https://pontoon.example.com'
PONTOON_ENTITIES_URL = PONTOON_URL + '/get-entities/'
PONTOON_HISTORY_URL = PONTOON_URL + '/get-history'
PONTOON_GRAPHQL_URL = PONTOON_URL + '/graphql'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    entities = read_file(PONTOON_ENTITIES)
    httpretty.register_uri(httpretty.POST,
                           PONTOON_ENTITIES_URL,
                           body=entities)

    history = read_file(PONTOON_HISTORY)
    httpretty.register_uri(httpretty.GET,
                           PONTOON_HISTORY_URL,
                           body=history)


def setup_graphql_server():
    locales_file = read_file(PONTOON_LOCALES)

    http_requests = []

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        body = locales_file
        http_requests.append(last_request)
        return 200, headers, body

    httpretty.register_uri(httpretty.GET,
                           PONTOON_GRAPHQL_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    return http_requests


class TestPontoonBackend(unittest.TestCase):
    """Pontoon backend tests"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        pontoon = Pontoon(uri=PONTOON_URL,
                          locale='es',
                          tag='test',
                          max_items=10)

        self.assertEqual(pontoon.uri, PONTOON_URL)
        self.assertEqual(pontoon.locale, 'es')
        self.assertEqual(pontoon.tag, 'test')
        self.assertEqual(pontoon.max_items, 10)

        # When tag is empty or None it will be set to
        # the value in the origin
        pontoon = Pontoon(PONTOON_URL, 'es')
        self.assertEqual(pontoon.uri, PONTOON_URL)
        self.assertEqual(pontoon.tag, 'https://pontoon.example.com/es')

        pontoon = Pontoon(PONTOON_URL, 'es', tag='')
        self.assertEqual(pontoon.uri, PONTOON_URL)
        self.assertEqual(pontoon.tag, 'https://pontoon.example.com/es')

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(Pontoon.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Pontoon.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of entities"""

        setup_http_server()

        expected = [
            [280952, "9dc5c9c9cb1319c7cd397f12570632f7a152af5a", "amo"],
            [292898, "11e2e9a975bc4ac9e5447464666553c9bce6a431", "amo"],
            [279094, "8207b2c6fcc9e3a76ae531a61f6611f8486c7f3f", "amo-linter"],
            [279120, "d5c7b016f4f6d7dacad3a41e9f60323da210be2a", "amo-linter"],
            [279115, "b35d5661eaf4262c0b45a7e233df578a52663606", "amo-linter"]
        ]

        backend = Pontoon(PONTOON_URL, 'es')
        entities = [e for e in backend.fetch()]

        self.assertEqual(len(entities), len(expected))

        for i, entity in enumerate(entities):
            self.assertEqual(entity['backend_name'], 'Pontoon')
            self.assertEqual(entity['origin'], 'https://pontoon.example.com/es')
            self.assertEqual(entity['tag'], 'https://pontoon.example.com/es')
            self.assertEqual(entity['category'], 'entity')
            self.assertEqual(entity['data']['pk'], expected[i][0])
            self.assertEqual(entity['uuid'], expected[i][1])
            self.assertEqual(entity['data']['project']['slug'], expected[i][2])
            self.assertEqual(len(entity['data']['history_data']), 4)

    @httpretty.activate
    def test_fetch_locale(self):
        """Test whether it fetches the available locales"""

        setup_graphql_server()

        expected = [
            ['ab', '02ba8534699aeadcd39874462fb411486cbb156b'],
            ['ace', '3df7b0d8d3526db5032f2b1d4db635e7ed5fc631'],
            ['ach', '3ec24c3ea3af0c8e00ecdb7d3a9808e671a7658f']
        ]

        backend = Pontoon(PONTOON_URL)
        locales = [loc for loc in backend.fetch(category='locale')]

        self.assertEqual(len(locales), len(expected))
        for i, locale in enumerate(locales):
            self.assertEqual(locale['data']['locale'], expected[i][0])
            self.assertEqual(locale['data']['url'], PONTOON_URL)
            self.assertEqual(locale['origin'], PONTOON_URL)
            self.assertEqual(locale['tag'], PONTOON_URL)
            self.assertEqual(locale['category'], 'locale')
            self.assertEqual(locale['uuid'], expected[i][1])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        backend = Pontoon(PONTOON_URL, 'es')
        entities = [e for e in backend.fetch()]

        for entity in entities:
            self.assertEqual(backend.metadata_id(entity['data']), entity['search_fields']['item_id'])


class TestPontoonCommand(unittest.TestCase):
    """Tests for PontoonCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Pontoon"""

        self.assertIs(PontoonCommand.BACKEND, Pontoon)

    def test_setup_cmd_parser(self):
        """Test if the parser object is correctly initialized"""

        parser = PontoonCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Pontoon)

        args = [
            PONTOON_URL,
            'es',
            '--tag', 'test',
            '--from-date', '2020-01-01',
            '--max-items', '10'
        ]
        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.uri, PONTOON_URL)
        self.assertEqual(parsed_args.locale, 'es')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.from_date, datetime.datetime(2020, 1, 1, tzinfo=tzutc()))


class TestPontoonClient(unittest.TestCase):
    """Tests for Pontoon client class"""

    def test_init(self):
        """Test initialization"""

        client = PontoonClient(base_uri=PONTOON_URL,
                               max_items=30)

        self.assertIsInstance(client, PontoonClient)
        self.assertEqual(client.base_url, PONTOON_URL)
        self.assertEqual(client.max_items, 30)

    @httpretty.activate
    def test_entities(self):
        """Test fetch entities for a locale"""

        # Mock HTTP server
        history = read_file(PONTOON_HISTORY)
        httpretty.register_uri(httpretty.GET,
                               PONTOON_HISTORY_URL,
                               body=history)

        bodies = [
            read_file(PONTOON_ENTITIES)
        ]
        http_requests = []

        def request_callback(method, uri, headers):
            last_request = httpretty.last_request()
            http_requests.append(last_request)
            body = bodies.pop(0).encode('utf-8')
            return [200, headers, body]

        httpretty.register_uri(httpretty.POST,
                               PONTOON_ENTITIES_URL,
                               body=request_callback,
                               status=200)

        # Expected results
        entities_data = json.loads(read_file(PONTOON_ENTITIES))
        history_data = json.loads(read_file(PONTOON_HISTORY))

        expected_0 = entities_data['entities'][0]
        expected_0['history_data'] = history_data
        expected_0['locale'] = 'es'
        expected_1 = entities_data['entities'][1]
        expected_1['history_data'] = history_data
        expected_1['locale'] = 'es'

        req_body = {
            'limit': ['5'],
            'locale': ['es'],
            'page': ['1'],
            'project': ['all-projects'],
            'time': ['202401010000-210001010000']
        }

        # Call API
        client = PontoonClient(base_uri=PONTOON_URL,
                               max_items=5)

        from_date = datetime.datetime(2024, 1, 1)
        entities = [e for e in client.fetch_entities('es', from_date=from_date)]
        self.assertDictEqual(entities[0], expected_0)
        self.assertDictEqual(entities[1], expected_1)

        self.assertEqual(len(http_requests), 1)
        self.assertEqual(http_requests[0].method, 'POST')
        self.assertEqual(http_requests[0].parsed_body, req_body)

    @httpretty.activate
    def test_history(self):
        """Test History for an entity request"""

        setup_http_server()

        history_data = json.loads(read_file(PONTOON_HISTORY))

        # Call API
        client = PontoonClient(base_uri=PONTOON_URL,
                               max_items=5)
        history = client.history(1234, 'es')

        self.assertEqual(history_data, history)

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertEqual(req.path, '/get-history?entity=1234&locale=es&plural_form=-1')

    @httpretty.activate
    def test_entities_pagination(self):
        """Test Emails/query request with pagination"""

        # Set up a mock HTTP server
        history = read_file(PONTOON_HISTORY)
        httpretty.register_uri(httpretty.GET,
                               PONTOON_HISTORY_URL,
                               body=history)

        bodies = [
            read_file(PONTOON_PAGE_1),
            read_file(PONTOON_PAGE_2)
        ]

        http_requests = []

        def request_callback(method, uri, headers):
            last_request = httpretty.last_request()
            http_requests.append(last_request)
            body = bodies.pop(0).encode('utf-8')
            return [200, headers, body]

        httpretty.register_uri(httpretty.POST,
                               PONTOON_ENTITIES_URL,
                               body=request_callback,
                               status=200)

        # Expected results
        expected_entities = [280952, 292898, 279094, 279120,
                             279115, 279124, 279138, 279144,
                             279140, 279123]
        req_body_0 = {
            'limit': ['5'],
            'locale': ['es'],
            'page': ['1'],
            'project': ['all-projects'],
            'time': ['197001010000-210001010000']
        }

        req_body_1 = {
            'limit': ['5'],
            'locale': ['es'],
            'page': ['2'],
            'project': ['all-projects'],
            'time': ['197001010000-210001010000']
        }

        # Call API
        client = PontoonClient(base_uri=PONTOON_URL,
                               max_items=5)
        entities = [e for e in client.fetch_entities('es')]

        self.assertEqual(len(list(entities)), 10)

        for i, entity in enumerate(entities):
            self.assertEqual(entity['pk'], expected_entities[i])

        self.assertEqual(len(http_requests), 2)

        req = http_requests[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.path, '/get-entities/')
        self.assertDictEqual(req.parsed_body, req_body_0)

        req = http_requests[1]
        self.assertEqual(req.method, 'POST')
        self.assertRegex(req.path, '/get-entities/')
        self.assertDictEqual(req.parsed_body, req_body_1)

    @httpretty.activate
    def test_locales(self):
        """Test fetch locales using the client"""

        http_requests = setup_graphql_server()

        # Expected results
        json.loads(read_file(PONTOON_LOCALES))

        expected = [
            {'locale': 'ab', 'url': 'https://pontoon.example.com'},
            {'locale': 'ace', 'url': 'https://pontoon.example.com'},
            {'locale': 'ach', 'url': 'https://pontoon.example.com'}
        ]

        # Call API
        client = PontoonClient(base_uri=PONTOON_URL,
                               max_items=5)

        locales = [loc for loc in client.fetch_locales()]
        for i, locale in enumerate(locales):
            self.assertDictEqual(locale, expected[i])

        self.assertEqual(len(http_requests), 1)
        self.assertEqual(http_requests[0].method, 'GET')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
