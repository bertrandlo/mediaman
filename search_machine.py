import queue
import time
import urllib
from datetime import datetime
from threading import Event
from queue import Queue

import requests
from PyQt5 import QtCore
from bs4 import BeautifulSoup, Tag
from torrentool.bencode import Bencode

from utils import keyword_extract


class Linker:
    tag = None
    title = None
    link = None
    magnet = None
    size = None
    Date = None
    seed_count = None

    def __init__(self, tag: Tag):
        self.tag = tag
        keys = [3, 4, 5]
        content = list(tag.find_all('td'))
        self.title = str(content[1].find('a').contents[0])
        info = [content[key].string for key in keys]
        self.size = content[3].string
        self.date = datetime.strptime(content[4].string, '%Y-%m-%d %H:%M')
        self.seed_count = int(content[5].string)
        self.magnet = tag.find_all('a')[-1].get('href')

    def __str__(self):
        return "{}\t{}\t{}".format(self.date, self.seed_count, self.magnet)


def query_by_keyword(keyword, page=None):
    if page is not None and page > 1:
        response = requests.get("https://sukebei.nyaa.si/?f=0&c=2_0&q={}&s=seeders&o=desc&p={}".format(keyword, page))
    else:
        response = requests.get("https://sukebei.nyaa.si/?f=0&c=2_0&q={}&s=seeders&o=desc".format(keyword))

    soup = BeautifulSoup(response.content, 'html5lib').find_all("div", {"class": "table-responsive"})
    magnet_list = soup[0].find_all('tbody')[0].findAll('tr')
    return magnet_list


class SearchMachine(QtCore.QThread):

    result = Queue()
    signal_searching_keyword = QtCore.pyqtSignal(str, int)
    signal_searching_finished = QtCore.pyqtSignal()
    signal_page_change = QtCore.pyqtSignal(int)
    signal_update_label = QtCore.pyqtSignal(str)
    signal_refresh = QtCore.pyqtSignal()
    flag_exit = Event()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.signal_page_change.connect(lambda delta: self.searching(self.job.keyword, self.job.page + delta))
        self.signal_searching_keyword.connect(self.searching)

    @QtCore.pyqtSlot(str)
    def download_torrent(self, url):
        print(url)
        r = requests.get(url)
        r.encoding = 'utf-8'
        # 取得對方預設的檔名
        fn = r.headers['content-disposition'].split('filename*=UTF-8')[1].strip("''").encode('iso-8859-1').decode('utf-8', "ignore")

        # faked urlretrieve header
        opener = urllib.request.build_opener()
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
        urllib.request.install_opener(opener)
        urllib.request.urlretrieve(url, 'C:\\Users\\brt\\Downloads\\'+fn)
        QtCore.QTimer.singleShot(100, lambda: self.signal_Update_Label.emit("完成下載 "+fn))
        bt_content = Bencode.read_file('C:\\Users\\brt\\Downloads\\' + fn)

        #qfinfo = QtCore.QFileInfo(item[0])

        if 'name.utf-8' in bt_content['info']:
                print(bt_content['info']['name.utf-8'])
                print(keyword_extract(bt_content['info']['name.utf-8']))
        else:
                print(bt_content['info']['name'])
                print(keyword_extract(bt_content['info']['name']))

    @QtCore.pyqtSlot(str, int)
    def searching(self, keyword, page=1):
        self.result.empty()

        for tag in query_by_keyword(keyword, page):
            link = Linker(tag)
            self.result.put_nowait(link)

        self.signal_refresh.emit()

    def run(self) -> None:
        while True:
            if self.flag_exit.isSet():
                break

            time.sleep(0.05)

        print("Searching Thread EXIT")
