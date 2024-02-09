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
import logging

import dateutil.tz

from grimoirelab_toolkit.datetime import str_to_datetime, datetime_to_utc
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...errors import BackendError

CATEGORY_ENTITY = 'entity'
CATEGORY_LOCALE = 'locale'

MAX_ITEMS_PER_PAGE = 200

DEFAULT_DATETIME = datetime.datetime(1970, 1, 1, 0, 0, 0,
                                     tzinfo=dateutil.tz.tzutc())
DEFAULT_LAST_DATETIME = datetime.datetime(2100, 1, 1, 0, 0, 0,
                                          tzinfo=dateutil.tz.tzutc())

logger = logging.getLogger(__name__)


class Pontoon(Backend):
    """Pontoon backend for Perceval.

    This class retrieves the entities and the list of locales
    from Pontoon.
    Initialize this class passing the URL of a Pontoon server.
    The origin of the data will be set to the value of `uri`.

    :param uri: URI of the Pontoon server
    :param locale: locale used to fetch the entities
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_ENTITY, CATEGORY_LOCALE]

    DATE_FIELD = 'date_created'
    ENTITY_ID_FIELD = 'pk'

    def __init__(self, uri, locale=None, tag=None, archive=None,
                 max_items=MAX_ITEMS_PER_PAGE, ssl_verify=True):
        if locale:
            origin = urijoin(uri, locale)
        else:
            origin = uri

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.uri = uri
        self.locale = locale
        self.max_items = max_items

        self.client = None

    def fetch(self, category=CATEGORY_ENTITY, filter_classified=False,
              from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME):
        """Fetch the items from a Pontoon server.

        The method retrieves from Pontoon the items.

        :param category: the category of items to fetch
        :param filter_classified: remove classified fields from the resulting items
        :param from_date: obtain translations created since this date
        :param to_date: obtain translations until a specific date

        :returns: a generator of items
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        from_date = datetime_to_utc(from_date)
        to_date = datetime_to_utc(to_date)

        kwargs = {
            'from_date': from_date,
            'to_date': to_date
        }
        items = super().fetch(category,
                              filter_classified=filter_classified,
                              **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the items.

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        to_date = kwargs['to_date']

        if category == CATEGORY_ENTITY:
            logger.info(f"Fetching entities on '{self.origin}' from {from_date} to {to_date}")
            items = self.client.fetch_entities(locale=self.locale, from_date=from_date, to_date=to_date)
        else:
            logger.info(f"Fetching locales on '{self.uri}'")
            items = self.client.fetch_locales()

        return items

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend does not support items archive
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a translation item."""

        if Pontoon.ENTITY_ID_FIELD in item:
            return str(item[Pontoon.ENTITY_ID_FIELD])
        else:
            return item['locale']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a translation item.

        The timestamp is extracted from the newest translation.
        If there are no translations available, the date defaults
        to when the entity was created.
        This date is converted to UNIX timestamp format.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """

        if 'history_data' not in item:
            return datetime.datetime.now().timestamp()

        date = None
        for tr in item['history_data']:
            ts = str_to_datetime(tr['date'])
            if not date or ts > date:
                date = ts
        if not date:
            date = str_to_datetime(item['date_created'])

        return date.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from each item.

        This backend generates 'entity' or 'locale' items.
        """
        if 'history_data' in item:
            return CATEGORY_ENTITY
        else:
            return CATEGORY_LOCALE

    def _init_client(self, from_archive=False):
        """Init client"""

        return PontoonClient(base_uri=self.uri, max_items=self.max_items)


class PontoonClient(HttpClient):
    """Client for retrieving entities and the list of locales
     from Pontoon.

    :param base_uri: Base URL of the Pontoon web application
    :param max_items: max number of translations items per query
    """

    # API RESOURCES
    RENTITIES = 'get-entities'
    RHISTORY = 'get-history'
    RGRAPHQL = 'graphql'
    QUERY_LOCALES = """
    {
        locales {
          code
        }
    }
    """

    def __init__(self, base_uri, max_items=MAX_ITEMS_PER_PAGE):
        self.max_items = max_items

        headers = {'x-requested-with': 'XMLHttpRequest'}
        super().__init__(base_url=base_uri, extra_headers=headers)

    def fetch_entities(self, locale, project='all-projects', from_date=DEFAULT_DATETIME,
                       to_date=DEFAULT_LAST_DATETIME):
        """Get the entities and history

        :param locale: locale to search
        :param project: project to search, 'all-projects' for all
        :param from_date: obtain translations created since this date
        :param to_date: obtain translations until a specific date
        """
        from_date = from_date.strftime("%Y%m%d%H%M")
        to_date = to_date.strftime("%Y%m%d%H%M")
        date_range = f'{from_date}-{to_date}'
        if not locale:
            cause = "Locale option is required to fetch entities."
            raise BackendError(cause=cause)

        eprocessed = []
        body = {
            'locale': locale,
            'project': project,
            'limit': self.max_items,
            'time': date_range
        }

        while True:
            path = f"{self.base_url.rstrip('/')}/{self.RENTITIES}/"
            r = self.fetch(path, payload=body, method=self.POST)
            data = r.json()

            for entity in data['entities']:
                eprocessed.append(entity['pk'])
                entity['history_data'] = self.history(entity['pk'], locale)
                entity['locale'] = locale
                yield entity

            if not data['has_next'] or not data['entities']:
                break

            exclude_ids = ','.join(str(i) for i in eprocessed)
            body['exclude_entities'] = exclude_ids

    def history(self, entity, locale):
        """Get history for an entity and locale"""

        path = urijoin(self.base_url, self.RHISTORY)
        payload = {'entity': entity, 'locale': locale, 'plural_form': -1}
        r = self.fetch(path, payload=payload)
        return r.json()

    def fetch_locales(self):
        """Get all the locales available"""

        path = urijoin(self.base_url, self.RGRAPHQL)
        params = {'query': self.QUERY_LOCALES}
        r = self.fetch(path, payload=params)
        data = r.json()

        for locale in data['data']['locales']:
            data = {
                'url': self.base_url,
                'locale': locale['code']
            }
            yield data


class PontoonCommand(BackendCommand):
    """Class to run Pontoon backend from the command line."""

    BACKEND = Pontoon

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Pontoon argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              to_date=True)
        # Required arguments
        group = parser.parser.add_argument_group('Pontoon arguments')
        group.add_argument('uri',
                           help="URL of the Pontoon server")
        group.add_argument('locale', nargs='?', default=None, type=str,
                           help="Locale to fetch entities.")
        group.add_argument('--max-items', dest='max_items',
                           default=MAX_ITEMS_PER_PAGE, type=int,
                           help="Max number of items per query.")

        return parser
