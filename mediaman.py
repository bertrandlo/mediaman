import logging
import multiprocessing
import os
import random
import requests
import string
import sys
import tempfile
import threading

from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import Qt  # some flags definition
from bs4 import BeautifulSoup
from send2trash import send2trash
from urllib3.exceptions import InsecureRequestWarning

import ffmpeg_ui
import managepanel
import websearch
from treeviewfolder import TreeViewFolder
from utils import keyword_extract


def get_human_readable(size, precision=1):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffix_index = 0
    while size > 1024 and suffix_index < 4:
        suffix_index += 1  # increment the index of the suffix
        size = size/1024.0  # apply the division
    return "%.*f%s" % (precision, size, suffixes[suffix_index])


def remove_dir(dirName):
    result = True
    qdir = QtCore.QDir(dirName)
    if qdir.exists(dirName):
        for info in qdir.entryInfoList(QtCore.QDir.NoDotAndDotDot | QtCore.QDir.System | QtCore.QDir.Hidden | QtCore.QDir.AllDirs | QtCore.QDir.Files, QtCore.QDir.DirsFirst):
            if info.isDir():
                result = remove_dir(info.absoluteFilePath())
            else:
                result = QtCore.QFile().remove(info.absoluteFilePath())

            if not result:
                return result

        result = qdir.rmdir(dirName)
    return result


def fn_web_searching(keywords: list, file_model: QtWidgets.QFileSystemModel, signal_msgbox_show):
    """
    搜尋 https://www.arzon.jp 並依據結果 直接更改目錄名稱 或 顯示結果
    :param keywords:
    :param file_model:
    :param signal_msgbox_show: 顯示訊息對應的信號物件
    :return:
    """
    # urllib3.disable_warnings()
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    for job in keywords:
        keyword, full_new_name, m = keyword_extract(job[0])
        print(file_model.fileInfo(job[1]).absoluteFilePath(), keyword)

        if m:
            db_url = "https://www.arzon.jp"
            session = requests.session()
            r = session.get(
                db_url + '/index.php?action=adult_customer_agecheck&agecheck=1&redirect=https%3A%2F%2Fwww.arzon.jp'
                         '%2Fitemlist.html%3Ft%3D%26m%3Dall%26s%3D%26q%3D' + keyword,
                verify=False)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, "html.parser")
            video_item = soup.find_all("dd", {"class": "entry-title"})

            if len(video_item) > 0:
                tmp = tempfile.mkstemp(suffix=".htm", prefix='output')  # [file_handle, filepathname]
                with open(tmp[1], 'w+', encoding='utf-8') as f:
                    actress_name_list = []
                    for video_item_idx in video_item:
                        for item in video_item_idx.find_all("a"):
                            print(db_url + item.get('href'))
                            f.write('<a href="' + db_url + item.get('href') + '">' + db_url + item.get('href') + "</a><br>")
                            item_info = session.get(db_url + item.get('href'), verify=False)
                            item_info.encoding = 'utf-8'
                            soup = BeautifulSoup(item_info.text, "html.parser")
                            item_register_info = soup.find("table", {"class": "item"})

                            for idx in item_register_info.find_all("tr"):
                                temp = idx.find_all("td")
                                if temp[0].text.strip(' \t\n\r') == 'AV女優：' and len(video_item) == 1:

                                    if not temp[1].text.strip(' \t\n\r'):
                                        actress_name = '素人'
                                    else:
                                        actress_name = temp[1].text.strip(' \t\n\r')

                                    print(actress_name, keyword, full_new_name)

                                    # 檢查是否有重複目錄
                                    dest_folder = file_model.fileInfo(job[1]).absolutePath() + QtCore.QDir.separator() + actress_name + '_' + full_new_name
                                    fn_rename_directory(file_model, dest_folder, job)

                                if temp[0].text.strip(' \t\n\r') == 'AV女優：':
                                    if not temp[1].text.strip(' \t\n\r'):
                                        actress_name = '素人'
                                    else:
                                        actress_name = temp[1].text.strip(' \t\n\r')

                                    actress_name_list.append(actress_name)

                                f.write(temp[0].text.strip(' \t\n\r'))  # 移除換行 空格 tab
                                f.write('<span>' + temp[1].text.strip(' \t\n\r') + '</span><br>\n')

                    if len(actress_name_list) > 1 and all(x == actress_name_list[0] for x in actress_name_list):
                        dest_folder = file_model.fileInfo(job[1]).absolutePath() + QtCore.QDir.separator() + actress_name + '_' + full_new_name
                        fn_rename_directory(file_model, dest_folder, job)
                        continue

                os.close(tmp[0])
                if len(video_item) > 1 or actress_name == '素人' or len(actress_name.splitlines()) > 1:  # 多於一位主演
                    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(tmp[1]))
            else:
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl('https://www.google.com.tw/?q=' + keyword + ' AV&lr=lang_zh-TW#q=' + keyword + ' AV&tabs=0'))
        else:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl('https://www.google.com.tw/?q=' + keyword + '&lr=lang_zh-TW#q=' + keyword + '&tabs=0'))


def fn_rename_directory(file_model, dest_folder, job):

    if QtCore.QDir(dest_folder).exists():

        # QtWidgets.QMessageBox('重複目錄名稱-'+dest_folder)
        # signalMsgboxShow.emit('重複目錄名稱 - '+dest_folder)
        appendixStr = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        QtCore.QDir().rename(file_model.fileInfo(job[1]).absoluteFilePath(), dest_folder + '-[重複]' + appendixStr)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl().fromLocalFile(dest_folder))

    else:
        QtCore.QDir().rename(file_model.fileInfo(job[1]).absoluteFilePath(), dest_folder)


def fnRename(strOldName, keyword=''):
    '''     提供一個共通的 regular express 用來修改或尋找檔名
    :param strOldName:
    :param keyword:
    :return:
    '''
    media_id, strNewName, m = keyword_extract(strOldName)

    if keyword != '':
        strNewName = keyword + '_' + strNewName

    return strNewName


class myQDirModel(QtWidgets.QFileSystemModel):

    def __init__(self, parent=None):
        super().__init__()
        self.setReadOnly(False)

    def supportedDropActions(self):
        return (Qt.CopyAction|Qt.MoveAction)


class filetable(QtWidgets.QTableView):

    selectedItems = []      # List of Selected Items by Filename
    itemCurrentSelected = None

    def __init__(self):
        super().__init__()

        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) #避免進入編輯狀態
        self.setSelectionMode(QtWidgets.QAbstractItemView.ContiguousSelection)

        self.setStyleSheet("::section{font-size:16px;Background-color:#D8D8D8;border:0px;} {font-size:16px;}")
        self.setStyleSheet("font-size:16px;Background-color:#D8D8D8;border:0px;")

        self.selection = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)
        self.selection.setVisible(False)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.customCxMenuEvent)

    def mousePressEvent(self, event):                                   #rectangle selection
        super().mousePressEvent(event)
        #self.setMouseTracking(True)
        if event.buttons() == Qt.LeftButton and not self.selection.isVisible():
            self.selection.origin = event.pos()
            self.selection.setGeometry(QtCore.QRect(self.selection.origin, QtCore.QSize()))
            self.selection.show()

    def mouseMoveEvent(self, event):    #利用 mouseMove 來檢查滑鼠按鍵
        super().mouseMoveEvent(event)
        if self.indexAt(event.pos()):
            item = self.indexAt(event.pos())
            model = self.model()
            if model.hasIndex(item.row(), item.column(), item.parent()):
                item = model.index(item.row(), 0, item.parent())
                self.selectionModel().select(item, QtCore.QItemSelectionModel.Select)
        try:
            self.selection.setGeometry(QtCore.QRect(self.selection.origin, event.pos()).normalized())
        except:
            pass

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setMouseTracking(False)
        self.selection.setGeometry(QtCore.QRect(self.selection.origin, event.pos()))
        #self.setSelection(QRect(self.selection.origin, event.pos()), QItemSelectionModel.Rows)

        self.selection.origin = event.pos()
        self.selection.hide()

    def setCurrentSelectedItem(self, widgetItem):
        if widgetItem.isSelected():
            self.itemCurrentSelected = widgetItem
        else:
            self.itemCurrentSelected = None

    def getSelectedItemsList(self):
        self.selectedItems = []
        #需要依據 filetable 換成 tableview/qfilesystemmodel 調整
        return self.selectedItems

    def file_info(self, idx):
        selFile = QtCore.QFile(self.model().filePath(idx))
        selFileInfo = QtCore.QFileInfo(selFile)
        file_location = selFileInfo.absolutePath()+QtCore.QDir.separator()+selFileInfo.baseName()+QtCore.QDir.separator()+selFileInfo.fileName()
        return selFile, selFileInfo, file_location

    def keyPressEvent(self, QKeyEvent): #覆寫內建的按鍵事件
        super(filetable, self).keyPressEvent(QKeyEvent)
        selFile, selFileInfo, file_location = self.file_info(self.selectedIndexes()[0])
        logging.debug(file_location)
        if QKeyEvent.key() == Qt.Key_F2 or QKeyEvent.key() == Qt.Key_Return:
            self.edit(self.selectedIndexes()[0])

    def customCxMenuEvent(self, pos):                           #右鍵選單 - QTableWidget

        if self.model().fileName(self.currentIndex()) == '':    #檢查是否有點選在項目上才顯示選單
            return

        cxmenu = QtWidgets.QMenu()
        act1 = QtWidgets.QAction('移入同名目錄', self)
        cxmenu.addAction(act1)
        action = cxmenu.exec_(self.viewport().mapToGlobal(pos))

        if action == act1:
            for idxItem in self.selectedIndexes():
                selFile, selFileInfo, file_location = self.file_info(idxItem)
                QtCore.QDir(selFileInfo.absolutePath()).mkdir(selFileInfo.baseName())
                logging.debug(selFileInfo.absolutePath()+QtCore.QDir.separator()+selFileInfo.baseName()+QtCore.QDir.separator()+selFileInfo.fileName())
                selFile.rename(selFileInfo.absolutePath()+QtCore.QDir.separator()+selFileInfo.baseName()+QtCore.QDir.separator()+selFileInfo.fileName())
            self.clearSelection()


class myFileListWidget(QtWidgets.QWidget):
    location = QtCore.QDir()
    myModel = myQDirModel()
    #myModel = QtWidgets.QFileSystemModel()
    #myModel.setRootPath(QtCore.QDir.currentPath())
    keypressed = QtCore.pyqtSignal(QtGui.QKeyEvent)
    revItemSrc = None
    #settings = QtCore.QSettings("candy", "brt")                # Registry Current_USER\Software\Candy\brt
    settings = QtCore.QSettings("settings.ini", QtCore.QSettings.IniFormat)

    signal_msgbox_show = QtCore.pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle('Files Manager')

        self.myModel.setReadOnly(False)
        self.myModel.supportedDropActions()

        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_DeleteOnClose)          #讓QT在最後一個視窗關閉時 自動清除全部 thread

        self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'icon.ico')))
        self.location = QtCore.QDir(self.settings.value("home", 'C:/Users/brt/Desktop/storage/BT/00-下載中'))

        self.myModel.setRootPath(self.settings.value("home", 'C:/Users/brt/Desktop/storage/BT/00-下載中'))
        style = """
                QWidget {
                    font-size:16px;
                    color: gray;
                    border: 2px solid #8f8f91; 
                    border-width:1px; 
                    border-style: solid;
                    background-color: #000000;
                    min-height:24px; 
                }

                QTreeView::item:selected {
                    background-color: #666;
                }
              
                QTableView::item:selected {
                    background-color: #666;
                }
                
                QMessageBox { messagebox-text-interaction-flags: 5; }
                
                QPushButton, QLineEdit {
                font-size:16px;
                border: 2px solid #8f8f91; border-width:1px; 
                border-radius:4px; 
                border-style: solid;
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde);
                min-height:24px; }

                QPushButton:pressed {
                    border: 2px solid #c0c0c0;
                }
                """
        self.setStyleSheet(style)

        self.msgbox = QtWidgets.QMessageBox(self)
        self.msgbox.hide()

        treeview = TreeViewFolder(self)
        treeview.setModel(self.myModel)

        treeview.setStyleSheet(style)
        treeview.header().setStretchLastSection(True)

        treeview.setRootIndex(self.myModel.index(self.location.absolutePath()))
        treeview.setSortingEnabled(True)
        treeview.setColumnWidth(0, 640)
        treeview.hideColumn(1)
        treeview.hideColumn(2)
        self.treeview = treeview

        fileinfo = filetable()
        fileinfo.setStyleSheet(style)
        fileinfo.setModel(myQDirModel())
        fileinfo.model().setRootPath(self.settings.value("home", 'C:/Users/brt/Desktop/storage/BT/00-下載中'))
        fileinfo.model().setFilter(QtCore.QDir.Files|QtCore.QDir.NoDotAndDotDot|QtCore.QDir.CaseSensitive)
        fileinfo.setRootIndex(fileinfo.model().index(self.location.absolutePath()))
        fileinfo.verticalHeader().setVisible(False)
        fileinfo.setSortingEnabled(True)
        fileinfo.setShowGrid(False)
        fileinfo.setEditTriggers(fileinfo.EditKeyPressed)
        fileinfo.hideColumn(2)
        fileinfo.setColumnWidth(0, 600)
        fileinfo.setColumnWidth(3, 200)
        #ileinfo.setCurrentIndex(fileinfo.model().index(self.location.absolutePath()))
        self.fileinfo = fileinfo

        self.myModel.setFilter(QtCore.QDir.NoDotAndDotDot|QtCore.QDir.AllDirs)
        self.myModel.setRootPath(self.location.absolutePath())

        locationline = QtWidgets.QLineEdit()
        locationline.setText(self.location.absolutePath())
        locationline.setStyleSheet(style)

        nameline = QtWidgets.QLineEdit()
        nameline.setStyleSheet("font-size: 14px;")
        self.nameline = nameline

        labelnameline = QtWidgets.QLabel("INFO")
        labelnameline.setStyleSheet("font-size: 14px;")

        labelMsg = QtWidgets.QLabel()
        labelMsg.setStyleSheet("font-size: 14px;")
        self.labelMsg = labelMsg

        btnSearch = QtWidgets.QPushButton("Database")
        btnSearch.setStyleSheet(style)
        btnWebService = QtWidgets.QPushButton("Web")
        btnWebService.setStyleSheet(style)
        btnFileConvert = QtWidgets.QPushButton("Convt")
        btnFileConvert.setStyleSheet(style)

        btnBack = QtWidgets.QPushButton("Back")
        btnBack.setStyleSheet(style)
        btnHome = QtWidgets.QPushButton('HDD')
        btnHome.setStyleSheet(style)

        layout = QtWidgets.QGridLayout()

        layout.addWidget(btnHome, 0, 0, 1, 1)
        layout.addWidget(btnBack, 0, 1, 1, 1)
        layout.addWidget(locationline, 0, 2, 1, 15)

        layout.addWidget(btnSearch, 0, 17, 1, 1)
        layout.addWidget(btnWebService, 0, 18, 1, 1)
        layout.addWidget(btnFileConvert, 0, 19, 1, 1)

        layout.addWidget(treeview, 1, 0, 9, 10)
        layout.addWidget(fileinfo, 1, 10, 9, 10)
        layout.addWidget(labelMsg, 10, 0, 1, 10, Qt.AlignLeft)
        layout.addWidget(labelnameline, 10, 10, 1, 1, Qt.AlignRight)
        layout.addWidget(nameline, 10, 11, 1, 9)

        #self.setStyleSheet("background-color: #D8D8D8;")
        self.setMinimumSize(800, 400)
        self.setLayout(layout)
        self.move(self.settings.value("pos", QtCore.QPoint(100,100)))
        self.resize(self.settings.value("size", QtCore.QSize(800, 400)))

        #Signal & Eent
        btnBack.clicked.connect(lambda: self.fnBtnBackClick(locationline))
        btnHome.clicked.connect(lambda: self.fnBtnHomeClick(locationline))

        #btnSearch.clicked.connect(lambda: self.win['searching'].show())
        btnSearch.clicked.connect(lambda: multiprocessing.Process(target=managepanel.main, daemon=True).start())
        btnWebService.clicked.connect(lambda: multiprocessing.Process(target=websearch.main, daemon=True).start())
        btnFileConvert.clicked.connect(lambda: multiprocessing.Process(target=ffmpeg_ui.main, daemon=True).start())

        locationline.returnPressed.connect(self.fnManualLocation)
        nameline.returnPressed.connect(self.fnItemRevName)
        treeview.doubleClicked.connect(lambda index: self.fnShowDirectoryinFinder(index))
        treeview.clicked.connect(lambda index: self.fnShowSubDir(index))
        fileinfo.doubleClicked.connect(lambda index: self.fnTableWidgetDbClick(index))
        fileinfo.clicked.connect(lambda index: self.fnShowFileBaseName(index, nameline))

        self.signal_msgbox_show.connect(lambda msg: self.fnShowMsg(msg), QtCore.Qt.QueuedConnection)

        self.fnManualLocation()
        self.win = {}
        #self.win['searching'] = catalogman.searchWidget(self)

    @QtCore.pyqtSlot(str)
    def fnShowMsg(self, msg):
        self.msgbox.setText(msg)
        self.msgbox.show()

    def fnShowDirectoryinFinder(self, index):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl().fromLocalFile(self.myModel.filePath(index)))

    def closeEvent(self, QMoveEvent):
        super(myFileListWidget, self).closeEvent(QMoveEvent)    #寫入需要儲存的參數
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("location", self.location.absolutePath())
        self.settings.sync()

        for client in self.win:
            self.win[client].destroy()                                    # 清除所有建構的子視窗

        self.deleteLater()                                                #多個視窗 避免退出錯誤

    def fnRefreshTreeview(self):

        treeview = self.layout().itemAtPosition(1, 0).widget()
        fileinfo = self.layout().itemAtPosition(1, 10).widget()
        locationline = self.layout().itemAtPosition(0, 2).widget()

        self.fnRenewFilelist(treeview.currentIndex(), treeview, fileinfo, locationline)

    def fnRenewFilelist(self, index, treeview, fileinfo, locationline):
        #RefreshFileList(self).run()
        pass

    def fnItemRevName(self):
        nameline = self.layout().itemAtPosition(10, 11).widget()
        fileinfo = self.layout().itemAtPosition(1, 10).widget()
        treeview = self.layout().itemAtPosition(1, 0).widget()
        locationline = self.layout().itemAtPosition(0, 2).widget()

        if self.revItemSrc == fileinfo:  #檔案

            qFile = QtCore.QFileInfo(fileinfo.fileitems[fileinfo.selectedItems[-1]])
            revFileName = self.location.absolutePath().append(QtCore.QDir.separator()).append(nameline.text()).append('.').append(qFile.suffix())

            try:
                fileinfo.fileitems[fileinfo.selectedItems[-1]].rename(revFileName)
                nameline.clear()
            except EnvironmentError as err:
                logging.debug(err.value)

            nameline.clearFocus()
            self.fnUpdateWorkingDirectory()

        if self.revItemSrc == treeview:   #目錄
            idxRownum = treeview.selectedIndexes()[0].row()
            qDir = QtCore.QDir(self.myModel.fileInfo(treeview.selectedIndexes()[0]).absoluteFilePath())
            newDir = QtCore.QDir(self.myModel.fileInfo(treeview.selectedIndexes()[0]).absoluteFilePath())
            newDir.cdUp()
            revDirName = newDir.absolutePath().append(QtCore.QDir.separator()).append(nameline.text())

            if QtCore.QDir.exists(revDirName):
                logging.debug("New Path Name Existed! Rename Failed.")
            else:
                try:
                    logging.debug(revDirName)
                    QtCore.QDir.rename(qDir.absolutePath(), revDirName)
                    nameline.clearFocus()
                    self.revItemSrc.setFocus()
                    self.revItemSrc.setCurrentIndex(QtWidgets.QDirModel().index(revDirName))

                except EnvironmentError as err:
                    logging.debug(err.value)

        self.revItemSrc = None

    def fnShowFileBaseName(self, index, nameline):
        nameline.setText(self.fileinfo.model().fileInfo(index).completeBaseName())
        self.fileinfo.getSelectedItemsList()

    def keyPressEvent(self, QKeyEvent): #覆寫內建的按鍵事件
        super(myFileListWidget, self).keyPressEvent(QKeyEvent)
        self.keypressed.emit(QKeyEvent)

    def fnBtnHomeClick(self, locationline):
        self.location.cd('C:/Users/brt/Desktop/storage/BT/00-下載中')
        locationline.setText('C:/Users/brt/Desktop/storage/BT/00-下載中')
        self.fnManualLocation()
        self.treeview.setFocus()

    def fnBtnBackClick(self, locationline):
        logging.debug('BACK')
        self.location.cdUp()
        locationline.setText(self.location.absolutePath())
        self.fnManualLocation()
        self.treeview.setFocus()

    def keyReleaseEvent(self, keyevent):
        #logging.debug('[KEY]' + QString.number(keyevent.key(), 16).toUpper())
        locationline = self.layout().itemAtPosition(0, 2).widget()

        if keyevent.matches(QtGui.QKeySequence().Paste):          #貼上 - 留待後續處理

            if self.focusWidget() == self.treeview or self.focusWidget() == self.fileinfo:   #只處理這兩個 widget
                clipboard = QtWidgets.QApplication.clipboard()    #檢查暫存區
                logging.debug(clipboard.mimeData().urls())
                for item in clipboard.mimeData().urls():
                    logging.debug(item)

        if keyevent.key() == Qt.Key_F4:  # F4  網頁搜尋 番號  + "演出" <- 需要 urlencoding

            keywords = []

            if self.focusWidget() == self.treeview:
                file_model = self.myModel
                for idx in self.treeview.selectedIndexes():
                    if idx.column() == 0:
                        keywords.append([self.myModel.fileName(idx), idx])

            if self.focusWidget() == self.fileinfo:
                file_model = self.fileinfo.model()
                for idx in self.fileinfo.selectedIndexes():
                    keywords.append([self.fileinfo.model().fileName(idx), idx])

            threading.Thread(target=fn_web_searching, kwargs={"keywords": keywords,
                                                            "file_model": file_model,
                                                            "signal_msgbox_show": self.signal_msgbox_show}).start()

        if keyevent.key() == Qt.Key_Delete:
            from pathlib import Path
            self.revItemSrc = self.focusWidget()

            if self.focusWidget() == self.treeview:         #刪除目錄
                logging.debug('刪除目錄')
                #idx = self.treeview.indexAt(self.treeview.mapFromGlobal(QCursor().pos()))
                idx = self.treeview.currentIndex()
                qdir = QtCore.QDir(self.myModel.filePath(idx))
                logging.debug(qdir.absolutePath())

                if qdir.exists():
                    self.treeview.setCurrentIndex(self.treeview.model().index(idx.row(), 0, idx.parent()))
                    threading.Thread(target=send2trash, kwargs={"path": str(Path(qdir.absolutePath()))}).start()    #利用執行緒進行刪除工作 避免UI停頓
                    self.fnShowSubDir(self.treeview.currentIndex())
                    self.labelMsg.setText('[DELETE]'+qdir.absolutePath())
                    logging.debug('[DELETE]'+qdir.absolutePath())

            if self.focusWidget() == self.fileinfo:         #刪除檔案

                print('刪除檔案')
                delFileListIndex = self.fileinfo.selectedIndexes()
                for idx in delFileListIndex:
                    threading.Thread(target=send2trash,
                                     kwargs={"path": str(Path(self.fileinfo.model().fileInfo(idx).absoluteFilePath()))}).start()
                    #Path(self.fileinfo.model().fileInfo(idx).absoluteFilePath()).unlink()
                    #send2trash(str(Path(self.fileinfo.model().fileInfo(idx).absoluteFilePath())))
                    self.labelMsg.setText('[DELETE]'+self.fileinfo.model().fileInfo(idx).absoluteFilePath())
                    logging.debug('[DELETE]'+self.fileinfo.model().fileInfo(idx).absoluteFilePath())

        if keyevent.key() == Qt.Key_F3:
            qrect = self.app.desktop().availableGeometry(self.app.desktop().screenNumber(self))
            width = qrect.width()
            height = (qrect.height()/2)
            logging.debug(qrect)
            border_x = (self.frameSize().width() - self.width())/2
            border_y = (self.frameSize().height() - self.height())/2
            self.setGeometry(QtWidgets.QApplication.desktop().screenGeometry(self.app.desktop().screenNumber(self)))

            if self.app.desktop().screenNumber(self) == 0:
                self.setGeometry(border_x, border_y, width-2*border_x, height-border_y*2)
            if self.app.desktop().screenNumber(self) == 1:
                self.setGeometry(border_x+self.app.desktop().availableGeometry(0).width(), border_y, width-2*border_x, height-border_y*2)

        if keyevent.key() == Qt.Key_Left:
            if self.focusWidget() == self.treeview:
                if self.treeview.state() != QtWidgets.QAbstractItemView.EditingState:
                    self.fnBtnBackClick(locationline)

        if keyevent.key() == Qt.Key_Enter or keyevent.key() == Qt.Key_Return:
            self.nameline = self.layout().itemAtPosition(10, 11).widget()
            #檢查按鍵焦點來源
            self.revItemSrc = self.focusWidget()

            if self.focusWidget() == self.treeview:         #目錄
                #logging.debug('[POS]'+self.myModel.fileInfo(self.treeview.indexAt(self.treeview.viewport().mapFromGlobal(QCursor().pos()))).absolutePath())
                if len(self.treeview.selectedIndexes()) == 0:
                    return
                idx = self.treeview.selectedIndexes()[0]
                #idx = self.myModel.index(self.location.absolutePath())
                self.nameline.setText(self.myModel.fileInfo(idx).fileName())
                #print(self.myModel.fileInfo(idx).absoluteFilePath())
                self.location = QtCore.QDir(self.myModel.fileInfo(idx).absoluteFilePath())
                locationline = self.layout().itemAtPosition(0, 2).widget()
                locationline.setText(self.myModel.fileInfo(idx).absoluteFilePath())
                locationline.returnPressed.emit()

    def fnTableWidgetDbClick(self, fileinfo):  #雙鍵點擊以系統預設關聯程式打開文件
        selFile = QtCore.QFile(self.location.absolutePath() + QtCore.QDir().separator() + fileinfo.model().fileName(fileinfo))
        logging.debug(QtCore.QUrl().fromLocalFile(selFile.fileName()))
        QtGui.QDesktopServices.openUrl(QtCore.QUrl().fromLocalFile(selFile.fileName()))

    def fnUpdateWorkingDirectory(self):

        fileinfo = self.fileinfo
        nameline = self.layout().itemAtPosition(10, 11).widget()
        if self.location.exists():

            x = 0
            fileinfo.fileitems = []
            for item in self.location.entryInfoList():
                if item.isHidden() | item.isDir() | item.isSymLink():
                    break;
                try:
                    fileinfo.insertRow(x)
                except:
                    break
                newItem = [QtWidgets.QTableWidgetItem(item.fileName()),
                           QtWidgets.QTableWidgetItem(get_human_readable(item.size())),
                           QtWidgets.QTableWidgetItem(item.lastModified().toString(Qt.ISODate))]
                fileinfo.setItem(x, 0, newItem[0])
                fileinfo.setItem(x, 1, newItem[1])
                fileinfo.setItem(x, 2, newItem[2])
                fileinfo.fileitems.append(QtCore.QFile(self.location.absolutePath().append(QtCore.QDir.separator()).append(item.fileName())))
                x = x+1

        nameline.clear()

    def fnShowSubDir(self, index):
        ''' 更新 self.location 與 右側檔案清單
        :param index: QModelIndex of Treeview CurrentIndex
        :return:
        '''
        locationline = self.layout().itemAtPosition(0, 2).widget()
        self.location = QtCore.QDir(self.myModel.filePath(index))

        # setRootPath 會把 QFileSystemModel 限定僅監看這個目錄下的結構變化 避免效率太低
        self.myModel.setRootPath(locationline.text())

        self.setWindowTitle('Files Manager - ' + self.location.absolutePath())
        filelistModel = self.fileinfo.model()
        idxList = filelistModel.setRootPath(self.location.absolutePath())   #很重要! 移動的要監看的目錄
        self.fileinfo.setRootIndex(idxList)
        self.fnUpdateWorkingDirectory()

        # 檢查目錄所在磁碟可用容量

        self.labelMsg.setText("可用容量 - " + get_human_readable(QtCore.QStorageInfo(self.location.absolutePath()).bytesAvailable()))

    def fnManualLocation(self):
        locationline = self.layout().itemAtPosition(0, 2).widget()
        self.location.setPath(locationline.text())
        self.treeview.setRootIndex(self.treeview.model().index(locationline.text()))
        self.fnUpdateWorkingDirectory()
        self.fnShowSubDir(self.treeview.model().index(locationline.text()))


def main():
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QtWidgets.QApplication(sys.argv)
    logging.debug(app.desktop().availableGeometry())
    widget = myFileListWidget(app)
    widget.thread().setObjectName('main thread')
    widget.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
