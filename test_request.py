import threading
import time
import unittest

import requests
from PyQt5 import QtCore
from bs4 import BeautifulSoup

from search_machine import SearchMachine, Linker


@QtCore.pyqtSlot()
def output():
    print("SIGNAL REFRESH")


class TestRequestCase(unittest.TestCase):

    def test_get_query(self):
        sm = SearchMachine()
        sm.searching('', 1)

        for link in sm.result:
            print(link.title, link)

    def test_threading_for_searching(self):
        search_vm = SearchMachine()
        search_vm.start()
        flag_exit: threading.Event
        flag_exit = search_vm.flag_exit

        search_vm.signal_refresh.connect(output)

        time.sleep(3)
        search_vm.signal_searching_keyword.emit('渋谷華', 1)
        time.sleep(2)
        for linker in list(search_vm.result.queue):
            print(linker)
        flag_exit.set()
        time.sleep(2)

    def test_load_hottest_links(self):
        response = requests.get("https://sukebei.nyaa.si/?s=seeders&o=desc")
        soup = BeautifulSoup(response.content, 'html5lib').find_all("div", {"class": "table-responsive"})
        result = soup[0].find_all('tbody')[0].findAll('tr')
        for tag in result:
            print(Linker(tag))
