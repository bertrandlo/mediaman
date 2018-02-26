#-*- coding: utf-8 -*-
import sys, os, re, logging, time
from threading import Thread
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtCore, QtGui
import formsearch

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)


class treeitem ():
    def __init__(self, nodeFileInfo, parentItem):
        '''
        :param nodeFileInfo: QFileInfo File/Dir
        :param parentItem:  linking to the parent node
        :return: Bool
        '''
        self.__child = []
        self.__row = None

        self.parentItem = parentItem
        self.__data = nodeFileInfo

    def appendChild(self, childItemFileInfo):
        '''
        :param childItemFileInfo: QFileInfo
        :return: row
        '''
        childItem = treeitem(childItemFileInfo, parentItem=self)
        self.__child.append(childItem)
        childItem.__row = len(self.__child)
        return childItem

    def data(self):
        if self.parent().parent() == None and self.childCount() > 0:
            return self.__data.absoluteFilePath().append(' (').append(QString().number(self.childCount())).append(')')
        else:
            return self.__data.absoluteFilePath()

    def child(self, row):
        '''
        :param row: row in tree model
        :return: treeitem
        '''
        return self.__child[row]

    def childCount(self):
        return len(self.__child)

    def parent(self):
        return self.parentItem

    def row(self):
        return self.__row

    def columnCount(self):
        return 1

    def GetHumanReadable(size,precision=1):
        suffixes=['B','KB','MB','GB','TB']
        suffixIndex = 0
        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1 #increment the index of the suffix
            size = size/1024.0 #apply the division
        return "%.*f%s"%(precision,size,suffixes[suffixIndex])


class treemodel(QAbstractItemModel):

    def __init__(self, rootItem, parent=None):
        super(treemodel, self).__init__(parent)
        self.rootItem = rootItem

    def columnCount(self, parent):
        if parent.isValid():                                               # QModelIndex::isValid()
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        if role != QtCore.Qt.DisplayRole:
            return None

        item = index.internalPointer()
        return item.data()

    def itemFromIndex(self, index):
        '''Returns the TreeItem instance from a QModelIndex.'''
        return index.internalPointer() if index.isValid() else self.rootItem

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def headerData(self, p_int, Qt_Orientation, int_role=None):                 #treemodel 必須實作才能正常顯示column標題
        if Qt_Orientation == Qt.Horizontal and int_role == Qt.DisplayRole:
            return QVariant(u'搜尋結果')
        return QVariant()

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def flags(self, QModelIndex):

        defaultFlags = QtCore.QAbstractItemModel.flags(self, QModelIndex)

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

        mimedata = super(treemodel, self).mimeData(indices)

        for index in indices:
            qfile = QFile(QFileInfo(self.data(index, Qt.DisplayRole)).absoluteFilePath())
            qfile.open(QIODevice.ReadOnly | QIODevice.Text)
            encodedData = qfile.readAll()
            fh = QString(self.data(index, Qt.DisplayRole))
            mimedata.setData("text/plain", encodedData)
            mimedata.setUrls([QtCore.QUrl.fromLocalFile(QFileInfo(self.data(index, Qt.DisplayRole)).absoluteFilePath())])
            qfile.close()

        return mimedata

class searchWidget(QWidget):

    searchProceeding = QtCore.pyqtSignal()
    searchingTimer = QtCore.QTimer()

    def __init__(self, parent=None):
        super(searchWidget, self).__init__()

        rootItem = treeitem(QFileInfo(QFile(QDir.homePath())), parentItem=None)
        self.treemodel = treemodel(rootItem)

        self.ui = formsearch.Ui_Form()
        self.ui.setupUi(self)
        self.settings = parent.settings
        self.ui.treeView.setModel(self.treemodel)

        # 沒有 reisze 與 close 按鈕的視窗 Qt.CustomizeWindowHint|Qt.WindowTitleHint
        self.progress = QtGui.QProgressDialog("", "Stop", 0, 100, self, QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint)
        self.progress.setWindowTitle('Searching Progress')
        #self.progress.setWindowModality(QtCore.Qt.WindowModal)

        self.ui.gridLayoutWidget.move(self.settings.value("pos", QPoint(100, 100)).toPoint()+QPoint(50, 50))
        #載入預設搜尋點
        self.settings = QSettings("candy", "brt")

        listSearchingPath = self.settings.value('searchingpath', [QDir.homePath()]).toStringList()
        idx = 0
        for item in listSearchingPath:
            self.ui.tableWidget.insertRow(self.ui.tableWidget.rowCount())
            self.ui.tableWidget.setItem(idx, 0, QTableWidgetItem(item))
            idx = idx + 1

        self.ui.btnSave.clicked.connect(self.fnSaveSearchPath)
        self.ui.btnSearch.clicked.connect(self.fnSearching)
        self.ui.treeView.doubleClicked.connect(self.treeviewDbClick)
        #self.searchProceeding.connect()
        #self.ui.tableWidget.doubleClicked.connect(self.fnAddRow)

    def fnProgressAdvanced(self, progress, threadPool, rootItem):

        progress.setValue(progress.value() + 1)
        result = 0

        for job in threadPool:
            if job.isAlive():
                result = result + 1

        if result == 0:
            self.searchingTimer.stop()
            progress.setValue(100)
            progress.reset()

            self.treemodel = treemodel(rootItem)
            self.ui.treeView.setModel(self.treemodel)
            self.searchingTimer.timeout.disconnect()

        else:
            predifinedValue = (100 / len(threadPool))*(len(threadPool)-result)
            if progress.value() < predifinedValue:
                progress.setValue(predifinedValue)
            self.treemodel = treemodel(rootItem)
            self.ui.treeView.setModel(self.treemodel)


        for idx in range(0, rootItem.childCount()):
            if rootItem.child(idx).childCount() < 10:
                self.ui.treeView.expand(self.treemodel.index(idx, 0, self.ui.treeView.rootIndex()))

    def fnGetSearchingPathList(self):
        listSearchingPath = []

        for idx in range(0, self.ui.tableWidget.rowCount(), 1):
            listSearchingPath.append(self.ui.tableWidget.item(idx, 0).text())
            logging.debug(listSearchingPath[-1])

        return listSearchingPath

    def threadSearching(self, strPath, strKeyWord, rootItem):

        node = rootItem.appendChild(QFileInfo(strPath))
        searchingResult = QDirIterator(strPath, QStringList([QString('*').append(strKeyWord).append(QString('*'))]), flags = QDirIterator.Subdirectories)
        self.searchProceeding.emit()
        while (searchingResult.hasNext()):
            result = searchingResult.next()
            logging.debug(result)
            node.appendChild(QFileInfo(result))

    def fnSearching(self):
        rootItem = treeitem(QFileInfo(QFile(None)), None)
        threadPool = []
        listSearchingPath = self.fnGetSearchingPathList()
        strKeyWord = self.ui.strKeyWord.text()

        self.progress.setValue(0)

        for strPath in listSearchingPath:
            threadPool.append(Thread(target=self.threadSearching, args=(strPath, strKeyWord, rootItem)))
            threadPool[-1].start()

        self.searchingTimer.timeout.connect(lambda: self.fnProgressAdvanced(self.progress, threadPool, rootItem))
        self.progress.setMinimumDuration(1000)
        self.searchingTimer.start(1000)          # update progressbar 1000ms

    def fnSaveSearchPath(self):
        self.settings.setValue("searchingpath", self.fnGetSearchingPathList())

    def treeviewDbClick(self, index):

        finfo = QFileInfo(QFile(index.data().toString()))
        if finfo.isFile():
            QtGui.QDesktopServices.openUrl(QUrl().fromLocalFile(finfo.dir().absolutePath()))
        else:
            QtGui.QDesktopServices.openUrl(QUrl().fromLocalFile(index.data().toString()))
