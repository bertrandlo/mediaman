# -*- coding: utf-8 -*-
import os
import sys
import re
import requests
import threading
import queue
import urllib.request
import pprint
import datetime
from torrentool.api import Torrent, Bencode

from utils import keyword_extract

from bs4 import BeautifulSoup
from PyQt5 import QtCore, QtWidgets, QtGui
from urllib3.exceptions import InsecureRequestWarning
from PyQt5.QtCore import Qt as Qt


class seed(QtCore.QObject):
    def __init__(self, **kwargs):
        """
        :param title:
        :param download_link:
        :param content_link:
        :param seed_num:
        """
        super().__init__()
        self.title = None
        self.download_link = None
        self.content_link = None
        self.seed_num = None
        self.added_time = None
        self.kwargs = kwargs
        for para in kwargs.keys():
            self.__setattr__(para, kwargs[para])


class myTableView(QtWidgets.QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == Qt.Key_Left:
            self.parent().on_Change_Page('prev')
            return

        if QKeyEvent.key() == Qt.Key_Right:
            self.parent().on_Change_Page('next')
            return

        if QKeyEvent.key() == Qt.Key_Return:
            if len(self.parent().table.selectedIndexes()) > 0:
                idx = self.parent().table.selectedIndexes()[0]
                # print(self.parent().seeds_list[idx.row()].content_link)
                threading.Thread(target=QtGui.QDesktopServices.openUrl,
                                 args=(QtCore.QUrl(self.parent().seeds_list[idx.row()].content_link),)).start()

                return

        super().keyPressEvent(QKeyEvent)


class ClickLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mouseDoubleClickEvent(self, *args, **kwargs):
        if len(self.parent().table.selectedIndexes()) > 0:
            idx = self.parent().table.selectedIndexes()[0]
            #print(self.parent().seeds_list[idx.row()].content_link)
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.parent().seeds_list[idx.row()].content_link))


class SearchMachine(QtCore.QObject):

    signal_Searching_Keyword = QtCore.pyqtSignal(str, int)
    signal_Download_Torrent = QtCore.pyqtSignal(str)
    signal_Searching_Finished = QtCore.pyqtSignal()
    signal_Page_Change = QtCore.pyqtSignal(int)
    # signal_Update_Label

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.thread_queue = queue.Queue(maxsize=1)
        self.signal_Searching_Keyword.connect(self.searching)
        self.signal_Page_Change.connect(lambda delta: self.searching(self.job.keyword, self.job.page + delta))
        self.signal_Download_Torrent.connect(self.download_torrent)

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
    def searching(self, keyword, page):

        if len(keyword) > 0:
            self.job = PageShell_Sukebei(page_url=r'/?page=search&cats=0_0&filter=0&term='+keyword,
                                         queue=self.thread_queue, seeds_minimum=1)
            self.job.page = 1
        else:
            self.job = PageShell_Sukebei(page_url='', queue=self.thread_queue, seeds_minimum=1)
            #self.job = PageShell_Extra(page_url=r'/category/533/Adult+-+Porn+Torrents.html?srt=added&order=desc', queue=self.thread_queue, seeds_minimum=1)

        #job = PageShell(base_url=r"https://sukebei.nyaa.se", page_url=r"/?page=search&cats=0_0&filter=0&term=", keyword=r"古川いおり")
        #job = PageShell_Sukebei(page_url="?offset=9", queue=thread_queue)
        #job = PageShell_Extra(base_url=r'https://extratorrent.cc', page_url=r'/view/yesterday/Adult+-+Porn.html?page=10&srt=added&order=desc&pp=50')

        self.job.keyword = keyword

        if page is not None and page > 1:
            self.job.page = page
        else:
            self.job.page = 1

        threading_grabpage = threading.Thread(target=self.job.grab_page)
        threading_grabpage.start()
        threading_grabpage.join()
        self.signal_Searching_Finished.emit()
        self.signal_Update_Label.emit('Page: ' + str(self.job.page))
        self.signal_Update_Window_Title.emit(str(page))


class TorrentWidget(QtWidgets.QWidget):

    signal_Update_Label = QtCore.pyqtSignal(str)
    signal_Update_Window_Title = QtCore.pyqtSignal(str)

    def __init__(self, parent: QtWidgets.QApplication):
        super().__init__()
        self.seeds_list = []
        self.result = None
        style = """
                QWidget {
                    font-size:16px;
                    color: #ddd;
                    border: 2px solid #8f8f91; 
                    border-width:1px; 
                    border-style: solid;
                    background-color: #000000;
                    min-height:24px; 
                }
                QHeaderView::section {
                    background-color: #000000;
                }
                QTableView {
                    border-radius:8px;
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #222, stop: 1 #333);
                }
                QTableView::item:selected {
                    background-color: #222;
                }
                """
        self.setWindowTitle('Torrent Browser')
        self.gridLayoutWidget = QtWidgets.QGridLayout()

        self.status_label = ClickLabel('Initialization')
        self.table = myTableView(self)
        self.table.setObjectName('table')
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.lineeditor = QtWidgets.QLineEdit()
        self.btn_nextpage = QtWidgets.QPushButton('&Next')
        self.btn_prevpage = QtWidgets.QPushButton('&Prev')

        self.gridLayoutWidget.addWidget(self.table,             0,  0,  19, 20)
        self.gridLayoutWidget.addWidget(self.status_label,      19, 0,  1,  14)
        self.gridLayoutWidget.addWidget(self.lineeditor,        19, 14, 1,  2)
        self.gridLayoutWidget.addWidget(self.btn_prevpage,      19, 16,  1,  2)
        self.gridLayoutWidget.addWidget(self.btn_nextpage,      19, 18,  1,  2)

        self.setLayout(self.gridLayoutWidget)
        self.setMinimumSize(800, 600)
        self.table.setAutoScroll(True)
        self.setStyleSheet(style)

        #self.table.setColumnWidth(0, self.table.width() - 60)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setStyleSheet(style)
        self.showMaximized()

    def signal_connect(self):
        self.table.pressed.connect(lambda index: self.on_table_pressed(index=index))
        self.lineeditor.returnPressed.connect(self.on_lineeditor_ReturnPressed)
        self.signal_Searching_Finished.connect(self.onRefreshTableView)
        self.signal_Update_Label.connect(lambda msg: self.status_label.setText(msg))
        self.table.doubleClicked.connect(lambda index: self.on_Table_DbClicked(index))
        self.btn_nextpage.clicked.connect(lambda: self.on_Change_Page('next'))
        self.btn_prevpage.clicked.connect(lambda: self.on_Change_Page('prev'))
        self.signal_Update_Window_Title.connect(lambda msg: self.setWindowTitle('Torrent Browser Page[' + msg + ']'))

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == Qt.Key_Escape:
            self.showMinimized()


    def on_Change_Page(self, action):
        if action == 'prev':
            self.signal_Page_Change.emit(-1)
        if action == 'next':
            self.signal_Page_Change.emit(1)

    @QtCore.pyqtSlot(object)
    def on_Table_DbClicked(self, index: QtCore.QModelIndex):
        download_link = (self.seeds_list[self.table.model().itemFromIndex(index).row()]).download_link
        print(download_link)
        self.signal_Download_Torrent.emit(download_link)

        #keyword_extract(item[0])

    def on_lineeditor_ReturnPressed(self):
        self.signal_Searching_Keyword.emit(self.lineeditor.text().strip(), 0)

    @QtCore.pyqtSlot()
    def onRefreshTableView(self):
        print('Renew Table Content')
        try:
            result = self.result.get(block=True, timeout=2)
        except queue.Empty as e:
            print('ERR Queue')
            return
        print('Renew Table Content Result Num - {}'.format(len(result),))

        #model = self.table.model()
        model = QtGui.QStandardItemModel()
        #model.clear()
        seeds_list = []

        for seed_object in result:
            try:
                #print(str(seed_object.seed_num), seed_object.size, seed_object.title)
                item = QtGui.QStandardItem(' [S: '+str(seed_object.seed_num)+'] ' + '['+seed_object.size+']' + str(seed_object.title))
            except AttributeError as e:
                print(e, seed_object, type(seed_object))
                continue

            model.appendRow([item])
            seeds_list.append(seed_object)

            try:
                if seed_object.seed_num >= 20:
                    model.setData(item.index(), QtGui.QBrush(Qt.red), Qt.ForegroundRole)

                if seed_object.seed_num < 10 and seed_object.seed_num >2:
                    model.setData(item.index(), QtGui.QBrush(Qt.darkGreen), Qt.ForegroundRole)

                if seed_object.seed_num <= 2:
                    model.setData(item.index(), QtGui.QBrush(Qt.darkYellow), Qt.ForegroundRole)

            except AttributeError as e:
                print(seed_object, e)
                continue

        self.result.task_done()

        self.seeds_list = seeds_list
        self.table.setModel(model)
        self.table.scrollToTop()
        self.table.selectRow(0)

    @QtCore.pyqtSlot(object)
    def on_table_pressed(self, index: QtCore.QModelIndex):
        model = self.table.model()
        threading.Thread(target=PageShell_Sukebei.seed_content,
                         args=(self.seeds_list[model.itemFromIndex(index).row()], self.result, self.signal_Update_Label)).start()


class PageShell_Sukebei(QtCore.QObject):
    def __init__(self, **kwargs):
        """
        :param queue: 讓執行緒可以把資料回傳 
        """
        super().__init__()
        # base_url = r'https://sukebei.nyaa.se/', page_url = '', keyword = ''
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        for para in kwargs.keys():
            self.__setattr__(para, kwargs[para])

        if not hasattr(self, 'base_url'):
            self.base_url = r'https://sukebei.nyaa.si/'

        self.search_result = []
        self.session = requests.session()

    def __grab__(self, url):
        self.search_result = []

        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

        r = self.session.get(url, headers=headers, verify=False)
        r.encoding = 'utf-8'
        content = BeautifulSoup(r.text, "html.parser")
        return content

    def grab_page(self, url=None):
        """
        :param url: 對應的搜尋網址 
        :param page: 搜尋結果的頁面數
        :return: None
        """
        # - 必須實作 Page Check
        if not hasattr(self, "page") or self.page == 1:
            content = self.__grab__(self.base_url + self.page_url).find_all('tr', 'default')
        else:
            if self.page_url == '':
                content = self.__grab__(self.base_url + '/?p='+str(self.page)).find_all('tr', 'default')
            else:
                content = self.__grab__(self.base_url + self.page_url + '&p=' + str(self.page)).find_all('tr', 'default')

        print('result - {}'.format(len(content)))

        seed_info = []
        fits = 0


        #print(content)

        for row in content:
            cmd = 'a.find_all("td", p)'
            #print(row)
            try:
                para = {'a': row, 'p': 'text-center'}
                #print(eval(cmd, para))
                seeds_num = int(eval(cmd, para)[-3].text)

            except ValueError:
                print(eval(cmd, para)[-3].text)
                seeds_num = 0
            except AttributeError:
                print(eval(cmd, para)[-3].text)
                seeds_num = 0

            cmd = 'a.find_all("td")'
            para = {'a': row}

            if eval(cmd, para)[0].a.get('title') == 'Art - Anime' or eval(cmd, para)[0].a.get('title') == 'Real Life - Videos':
                fits += 1
                # [分類, 下載連結, 標題, 檔案體積, 內容連結]
                #pprint.pprint(eval(cmd, para))
                #print(eval(cmd, para)[3])
                seed_info.append(seed(title=eval(cmd, para)[1].a.text.strip(),
                                      download_link=self.base_url[0:-1] + eval(cmd, para)[1].a['href']+'/torrent',
                                      content_link=self.base_url[0:-1] + eval(cmd, para)[1].a['href'],
                                      size=eval(cmd, para)[3].text.strip(),
                                      seed_num=seeds_num))

        print('Catalogy Fit - {}'.format(fits, ))

        if hasattr(self, "queue"):
            while self.queue.empty():
                try:
                    self.queue.put(seed_info, timeout=1)
                    break
                except queue.Full:
                    self.queue.get()
                    print('ERR Queue Full')

    @staticmethod
    def seed_content(seed_info: seed, result=None, signal_Update_Label=None):
        session = requests.session()
        chk_page = session.get(seed_info.content_link, verify=False)
        chk_page.encoding = 'utf-8'
        content = BeautifulSoup(chk_page.text, "html.parser")
        # print(r"https:"+item.a['href'])
        data = content.find_all('div', 'col-md-5')
        seed_time = datetime.datetime.utcfromtimestamp(int(data[1]['data-timestamp']))
        print(seed_time)
        # URL           Date            Seeds       Downloads
        msg = '[S: ' + str(seed_info.seed_num) + '][' + seed_info.size + ']' + " " + seed_time.strftime('%Y-%m-%d  %H:%M:%S')
        print(msg)

        if signal_Update_Label is not None:
            signal_Update_Label.emit(msg)


class PageShell_Extra(PageShell_Sukebei):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = r'https://extratorrent.cc'

        dcap = dict(webdriver.DesiredCapabilities.PHANTOMJS)
        dcap = {
            "phantomjs.page.settings.userAgent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.80 Safari/537.36",
            "phantomjs.page.settings.loadImages": False,
            "phantomjs.page.settings.resourceTimeout": 500
        }
        self.driver = webdriver.PhantomJS(desired_capabilities=dcap)
        self.driver.implicitly_wait(15)  # in seconds

    def __grab__(self, url):
        self.driver.get(url)
        return BeautifulSoup(self.driver.page_source, 'html.parser')  # javascript render page, using PhantomJS + selenium

    def grab_page(self, url=None):

        # - 必須實作 Page Check
        if not hasattr(self, "page") or self.page == 1:
            content = self.__grab__(self.base_url + self.page_url)
        else:
            if self.page_url == '':
                print(self.base_url + r'/category/533/Adult+-+Porn+Torrents.html?srt=added&order=desc&page='+str(self.page))
                content = self.__grab__(self.base_url + r'/category/533/Adult+-+Porn+Torrents.html?srt=added&order=desc&page='+str(self.page))
            else:
                print(self.base_url + self.page_url + r'&page=' + str(self.page))
                content = self.__grab__(self.base_url + self.page_url + r'&page=' + str(self.page))

        print('result - {}'.format(len(content.find_all('tr', 'tlr') + content.find_all('tr', 'tlz'))))

        seed_info = []
        idx = 0
        for row in content.find_all('tr', 'tlr') + content.find_all('tr', 'tlz'):
            idx += 1
            item_info = row.find_all('td')
            try:
                seed_num = int(item_info[4].text)
            except ValueError:
                seed_num = 0


            seed_info.append(seed(title=((item_info[1].find_all('a'))[0]).text,
                                  download_link=self.base_url + (item_info[0].find_all('a')[0])['href'],
                                  content_link='https:' + row.find('td', 'tli').a['href'],
                                  size=item_info[3].text,
                                  seed_num=seed_num))

        if hasattr(self, "queue"):
            while self.queue.empty():
                try:
                    self.queue.put(seed_info, timeout=1)
                    break
                except queue.Full:
                    self.queue.get()
                    print('ERR Queue Full')

    @staticmethod
    def seed_content(seed_info: seed, result=None, signal_Update_Label=None):
        # 取得完整的種子加入日期 seed_info.content_link
        chk_page.encoding = 'utf-8'
        content = BeautifulSoup(chk_page.text, "html.parser")
        # print(r"https:"+item.a['href'])
        data = content.find_all('td', 'vtop')
        # URL           Date            Seeds       Downloads
        msg = '[S: ' + str(seed_info.seed_num) + '][' + seed_info.size + ']' + " " + data[0].text
        print(msg)

        if signal_Update_Label is not None:
            signal_Update_Label.emit(msg)


def main():

    app = QtWidgets.QApplication(sys.argv)
    # 搜尋 py檔案所在的目錄內的 icon 檔案
    app.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'search-website-512.png')))

    widget = TorrentWidget(app)
    model = QtGui.QStandardItemModel()
    #model.setHorizontalHeaderItem(0, QtGui.QStandardItem("title"))
    widget.table.setModel(model)
    widget.table.horizontalHeader().hide()
    widget.thread().setObjectName('main thread')
    widget.show()

    thread_VM = QtCore.QThread(widget)  # 讓 thread_VM 能夠跟著 widget 關閉而自動結束
    thread_VM.setObjectName('thread_VM')
    thread_VM.start()

    searchVM = SearchMachine()
    searchVM.signal_Update_Label = widget.signal_Update_Label
    searchVM.signal_Update_Window_Title = widget.signal_Update_Window_Title
    searchVM.setObjectName('searchVM')
    searchVM.moveToThread(thread_VM)

    widget.result = searchVM.thread_queue

    widget.signal_Searching_Keyword = searchVM.signal_Searching_Keyword
    widget.signal_Searching_Finished = searchVM.signal_Searching_Finished
    widget.signal_Download_Torrent = searchVM.signal_Download_Torrent
    widget.signal_Page_Change = searchVM.signal_Page_Change
    widget.signal_connect()

    searchVM.signal_Searching_Keyword.emit('', 10)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
