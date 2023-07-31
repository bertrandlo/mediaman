import unittest

import requests
from bs4 import BeautifulSoup

from search_machine import query_by_keyword, SearchMachine
from torrent_window import Linker


class TestRequestCase(unittest.TestCase):

    def test_get_query(self):
        sm = SearchMachine()
        sm.searching('渋谷華', 1)

        for link in sm.result:
            print(link.title, link)

    def test_load_hottest_links(self):
        response = requests.get("https://sukebei.nyaa.si/?s=seeders&o=desc")
        soup = BeautifulSoup(response.content, 'html5lib').find_all("div", {"class": "table-responsive"})
        result = soup[0].find_all('tbody')[0].findAll('tr')
        for tag in result:
            print(Linker(tag))
