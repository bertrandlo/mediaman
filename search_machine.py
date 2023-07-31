from PyQt5 import QtCore
import queue
import threading
import requests
import urllib

from bs4 import BeautifulSoup
from torrentool.bencode import Bencode

from torrent_window import Linker
from utils import keyword_extract


def query_by_keyword(keyword, page=None):
    if page is not None and page > 1:
        response = requests.get("https://sukebei.nyaa.si/?f=0&c=0_0&q={}&s=seeders&o=desc&p={}".format(keyword, page))
    else:
        response = requests.get("https://sukebei.nyaa.si/?f=0&c=0_0&q={}&s=seeders&o=desc".format(keyword))

    soup = BeautifulSoup(response.content, 'html5lib').find_all("div", {"class": "table-responsive"})
    magnet_list = soup[0].find_all('tbody')[0].findAll('tr')
    return magnet_list

