#-*- coding: utf-8 -*-
import sys, os, re, logging, time, copy
from threading import Thread
from PyQt5.QtCore import *
from PyQt5 import QtWidgets, QtGui
import formsearch


class treeitem(QtGui.QStandardItem):
    def __init__(self, strPath):
        '''
        :param strPath: item path
        :return:
        '''
        super().__init__(strPath)
        self.qfileinfo = QFileInfo(strPath)
        self.count = 0

    def type(self):
        return QtGui.QStandardItem.UserType

    def GetHumanReadable(size,precision=1):
        suffixes=['B', 'KB', 'MB', 'GB', 'TB']
        suffixIndex = 0
        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1 #increment the index of the suffix
            size = size/1024.0 #apply the division
        return "%.*f%s"%(precision, size, suffixes[suffixIndex])


class TreemModel(QtGui.QStandardItemModel):                                 # 給 Searching Widget 使用的樹狀模型

    def __init__(self):
        super().__init__()

    def headerData(self, p_int, Qt_Orientation, int_role=None):                 #treemodel 必須實作才能正常顯示column標題
        if Qt_Orientation == Qt.Horizontal and int_role == Qt.DisplayRole:
            return '搜尋結果'
        return

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def flags(self, QModelIndex):

        defaultFlags = QAbstractItemModel.flags(self, QModelIndex)

        if QModelIndex.isValid():
            return Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | defaultFlags
        else:
            return Qt.ItemIsDropEnabled | defaultFlags

    def mimeTypes(self):
        return ['application/x-fileman-item', 'text/plain']

    def dropMimeData(self, QMimeData, Qt_DropAction, p_int, p_int_1, QModelIndex):
        return True

    def mimeData(self, indices):
        '''Encode serialized data from the item at the given index into a QMimeData object.'''

        mimedata = super(TreemModel, self).mimeData(indices)

        for index in indices:
            qfile = QFile(QFileInfo(self.data(index, Qt.DisplayRole)).absoluteFilePath())
            qfile.open(QIODevice.ReadOnly | QIODevice.Text)
            encodedData = qfile.readAll()
            fh = self.data(index, Qt.DisplayRole)
            mimedata.setData("text/plain", encodedData)
            mimedata.setUrls([QUrl.fromLocalFile(QFileInfo(self.data(index, Qt.DisplayRole)).absoluteFilePath())])
            qfile.close()

        return mimedata


class searchWidget(QtWidgets.QWidget):

    searchProceeding = pyqtSignal()
    progress = None
    threadPool = []

    def __init__(self, parent=None):
        super().__init__()

        #self.treemodel = QtGui.QStandardItemModel()
        self.treemodel = TreemModel()

        self.ui = formsearch.Ui_Form()
        self.ui.setupUi(self)
        self.settings = parent.settings
        self.ui.treeView.setModel(self.treemodel)
        self.threadPool = []

        self.searchingTimer = QTimer(self)              #QTimer 必須放在主 widget 才能隨著視窗事件被定時處理

        self.ui.gridLayoutWidget.move(self.settings.value("pos", QPoint(100, 100))+QPoint(50, 50))
        #載入預設搜尋點
        self.settings = QSettings("candy", "brt")

        listSearchingPath = self.settings.value('searchingpath', [QDir.homePath()])
        idx = 0
        for item in listSearchingPath:
            self.ui.tableWidget.insertRow(self.ui.tableWidget.rowCount())
            self.ui.tableWidget.setItem(idx, 0, QtWidgets.QTableWidgetItem(item))
            idx = idx + 1

        self.ui.strKeyWord.returnPressed.connect(self.fnSearching)
        self.ui.btnSave.clicked.connect(self.fnSaveSearchPath)
        self.ui.btnSearch.clicked.connect(self.fnSearching)
        self.ui.treeView.doubleClicked.connect(self.treeviewDbClick)

        self.searchingTimer.timeout.connect(self.fnProgressAdvanced, Qt.DirectConnection)
        #self.searchProceeding.connect()

    def fnProgressAdvanced(self):
        print('TICK')
        result = 0
        listSearchingPath = self.fnGetSearchingPathList()
        self.treemodel.clear()

        if len(self.threadPool) == 0:
            return

        for job in self.threadPool:
            if job[1].flag_JobFinish:
                job[0].quit()

            if job[0].isRunning():
                result += 1

        if result > 0:
            try:
                predifinedValue = round((100 / len(self.threadPool))*(len(self.threadPool)-result))
                print('Searching Job Complete - {}%'.format(str(predifinedValue)))
                if self.progress.value() < predifinedValue:
                    self.progress.setValue(predifinedValue)
                else:
                    self.progress.setValue(self.progress.value() + 1)
            except Exception as e:
                print(e)

            return

        idx = 0
        for strPath in listSearchingPath:
            path = treeitem(strPath)
            search_result = self.threadPool[idx][1].get_result()
            print(repr(search_result))
            if search_result is not None:
                path.appendColumn(search_result)

            self.treemodel.appendRow(path)
            idx += 1

        for idx in range(len(self.threadPool)):
            item = self.treemodel.item(idx)
            if item is not None:
                print('TreeItemText:'+item.text() + ' [' + str(item.rowCount()) + ']')
                item.setText(item.text() + ' [' + str(item.rowCount()) + ']')

            self.ui.treeView.expand(self.treemodel.index(idx, 0, self.ui.treeView.rootIndex()))

        for idx in range(self.ui.treeView.model().rowCount()):
            if self.ui.treeView.model().item(idx).rowCount() < 10:
                self.ui.treeView.setExpanded(self.ui.treeView.model().index(idx, 0), True)

        for item in self.threadPool:
            print(item[0].objectName() + ' - ' + str(item[0].isRunning()) + ' - flag_JobFinish - ' + str(item[1].flag_JobFinish))

        self.progress.setValue(100)
        self.progress.reset()
        #self.searchingTimer.timeout.disconnect(self.fnProgressAdvanced)
        self.searchingTimer.stop()
        print('Searching Finished.')


    def fnGetSearchingPathList(self):
        listSearchingPath = []

        for idx in range(0, self.ui.tableWidget.rowCount(), 1):
            listSearchingPath.append(self.ui.tableWidget.item(idx, 0).text())
            logging.debug(listSearchingPath[-1])

        return listSearchingPath

    def fnSearching(self):
        self.searchingTimer.start(50)  # update progressbar
        # fnProgressAdvanced 負責顯示進度與定時更新搜尋結果
        self.jobPool = []
        listSearchingPath = self.fnGetSearchingPathList()
        strKeyWord = self.ui.strKeyWord.text()

        progress = QtWidgets.QProgressDialog("Searching Progress", "Stop", 0, 100, self, Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.progress = progress
        progress.setWindowTitle('Searching Progress')
        progress.setValue(1)

        if len(strKeyWord) < 2:
            msgbox = QtWidgets.QMessageBox(icon=QtWidgets.QMessageBox.Warning, text='關鍵字太短')
            msgbox.setWindowFlags(Qt.Popup)
            msgbox.exec()
            return False

        # 沒有 reisze 與 close 按鈕的視窗 Qt.CustomizeWindowHint|Qt.WindowTitleHint

        progress.show()

        self.treemodel.clear()
        self.ui.treeView.setModel(self.treemodel)

        self.threadPool[:] = []

        for strPath in listSearchingPath:
            # QThread 改寫版本
            #QCoreApplication.processEvents()
            thread = QThread(objectName='thread-'+strPath)
            thread.start()
            job = searchingJob(strPath, strKeyWord)
            job.moveToThread(thread)
            job.signal_Run.emit()
            self.threadPool.append([thread, job])

    def fnSaveSearchPath(self):
        self.settings.setValue("searchingpath", self.fnGetSearchingPathList())

    def treeviewDbClick(self, index):

        finfo = index.model().itemFromIndex(index).qfileinfo
        if finfo.isFile():
            QtGui.QDesktopServices.openUrl(QUrl().fromLocalFile(finfo.dir().absolutePath()))
        else:
            QtGui.QDesktopServices.openUrl(QUrl().fromLocalFile(finfo.absoluteFilePath()))


class searchingJob(QObject):

    signal_Run = pyqtSignal()

    def __init__(self, strPath, strKeyWord):
        super().__init__()
        self.strPath = strPath
        self.strKeyWord = strKeyWord
        self.setObjectName('Searching Job - ' + strPath)
        self.result = None
        self.mutex = QMutex()
        self.signal_Run.connect(self.run, Qt.QueuedConnection)
        self.flag_JobFinish = False

    def get_result(self):
        result = copy.copy(self.result)
        return result

    @pyqtSlot()
    def run(self):
        print('Searching @ ' + QThread.currentThread().objectName())
        # 使用 QT 內建的搜尋功能 QDirIterator
        searchingResult = QDirIterator(self.strPath, ['*'+self.strKeyWord+'*'], flags=QDirIterator.Subdirectories)
        collect = []
        self.result = []
        while (searchingResult.hasNext()):
            result = searchingResult.next()
            collect.append(treeitem(result))
            self.mutex.lock()
            self.result = collect
            self.mutex.unlock()

        self.mutex.lock()
        self.flag_JobFinish = True
        self.mutex.unlock()
        self.thread().quit()
        return 0
