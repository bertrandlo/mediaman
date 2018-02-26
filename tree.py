# -*- coding: utf-8 -*-
from PyQt5 import QtGui, QtCore, QtWidgets
import sqlite3


class treeitem(QtGui.QStandardItem):
    def __init__(self, strPath):
        '''
        :param strPath: item path
        :return:
        '''
        super().__init__(strPath)
        self.qfileinfo = QtCore.QFileInfo(strPath)
        self.qdir = QtCore.QDir(strPath)
        self.ROWID = None
        self.count = 0

    def data(self, role=None, *args, **kwargs):
        if role is None or role == QtCore.Qt.DisplayRole:
            if self.rowCount() == 0:
                return super().data(QtCore.Qt.DisplayRole)
            else:
                return super().data(QtCore.Qt.DisplayRole) + ' [' + str(self.rowCount()) + ']'

        if role == QtCore.Qt.UserRole:      # 自訂回送對應目錄的 QFileInfo 物件
            return self.qfileinfo

    @property
    def depth(self):
        depth = 0
        parent = self.parent()
        try:
            while True:
                parent = parent.parent()
                depth += 1
        except AttributeError:
            return depth

    def deleteFile(self):
        if self.qfileinfo.exists():
            print('DELETE FILE - ' + self.qfileinfo.absoluteFilePath())
            return QtCore.QDir().remove(self.qfileinfo.absoluteFilePath())

    def type(self):
        return QtGui.QStandardItem.UserType

    def GetHumanReadable(size,precision=1):
        suffixes=['B', 'KB', 'MB', 'GB', 'TB']
        suffixIndex = 0
        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1 #increment the index of the suffix
            size = size/1024.0 #apply the division
        return "%.*f%s"%(precision, size, suffixes[suffixIndex])


class TreeView(QtWidgets.QTreeView):

    signal_Searching = None
    signal_item_clicked = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.clicked.connect(self.item_clicked)

    def keyPressEvent(self, qkeyevent: QtGui.QKeyEvent):
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

        if qkeyevent.key() == QtCore.Qt.Key_Delete and len(self.selectedIndexes()) > 0:
            delete_dict = {}
            for index in self.selectedIndexes():
                delete_dict[self.model().itemFromIndex(index).row()] = index
                QtWidgets.QApplication.processEvents()

            disk_item_index = self.selectedIndexes()[0].parent()

            # 從最下層的 row 開始刪除
            for row in sorted(delete_dict, reverse=True):
                self.model().removeIndex(delete_dict[row])
                QtWidgets.QApplication.processEvents()
            # <待處理> - 更新顯示搜尋的筆數
            QtWidgets.QApplication.restoreOverrideCursor()
            return

        QtWidgets.QApplication.restoreOverrideCursor()

    def item_clicked(self, idx: QtCore.QModelIndex):
        #print(index, index.row(), self.model().itemFromIndex(index).depth)
        if self.model().itemFromIndex(idx).depth == 0: # select all
            collection = QtCore.QItemSelection(self.model().index(0, 0, idx), self.model().index(self.model().rowCount(idx)-1, 0, idx))
            #QtCore.QItemSelectionModel().select(idx, QtCore.QItemSelectionModel.Deselect)
            sel = QtCore.QItemSelectionModel(self.model())
            sel.select(collection, QtCore.QItemSelectionModel.Select)
            self.setSelectionModel(sel)
            #print(collection, len(collection.indexes()))

        self.signal_item_clicked.emit(idx)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()
        data = QtGui.QDrag(self)
        data.setMimeData(event.mimeData())

    def dropEvent(self, event):
        event.acceptProposedAction()
        data = QtGui.QDrag(self)
        data.setMimeData(event.mimeData())
        data.start(QtCore.Qt.CopyAction)

    def startDrag(self, *args, **kwargs):
        super(TreeView, self).startDrag(*args, **kwargs)


class TreeModel(QtGui.QStandardItemModel):                                 # 給 Searching Widget 使用的樹狀模型

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn

    # VIEW 的整體呈現形式由 model 決定  VIEW主要處理操作的部分
    def data(self, index: QtCore.QModelIndex, role=None):
        item = self.itemFromIndex(index)
        if item.depth == 0 and role == QtCore.Qt.ForegroundRole:
            if QtCore.QStorageInfo(item.qfileinfo.absoluteFilePath()).isValid() and \
                    QtCore.QStorageInfo(item.qfileinfo.absoluteFilePath()).isReady():
                return QtGui.QColor(QtCore.Qt.white)
            else:
                return QtGui.QColor(QtCore.Qt.darkYellow)

        return super().data(index, role)

    def removeIndex(self, index: QtCore.QModelIndex):
        ROWID = self.itemFromIndex(index).ROWID
        if self.itemFromIndex(index).deleteFile():
            cur = self.conn.cursor()
            cur.execute("DELETE FROM files WHERE ROWID = ?", [ROWID])
            self.conn.commit()
            super().removeRow(self.itemFromIndex(index).row(), index.parent())

    def headerData(self, p_int, Qt_Orientation, int_role=None):                 #treemodel 必須實作才能正常顯示column標題
        if Qt_Orientation == QtCore.Qt.Horizontal and int_role == QtCore.Qt.DisplayRole:
            return '搜尋結果'
        return

    def supportedDropActions(self):
        return QtCore.Qt.CopyAction | QtCore.Qt.MoveAction

    def flags(self, QModelIndex):

        defaultFlags = QtCore.QAbstractItemModel.flags(self, QModelIndex)

        if QModelIndex.isValid():
            return QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled | defaultFlags
        else:
            return QtCore.Qt.ItemIsDropEnabled | defaultFlags

    def mimeTypes(self):
        return ['application/x-fileman-item', 'text/plain']

    def dropMimeData(self, QMimeData, Qt_DropAction, p_int, p_int_1, QModelIndex):
        return True

    def mimeData(self, indices):
        '''Encode serialized data from the item at the given index into a QMimeData object.'''

        mimedata = super(TreeModel, self).mimeData(indices)

        for index in indices:
            qfile = QtCore.QFile(QtCore.QFileInfo(self.data(index, QtCore.Qt.DisplayRole)).absoluteFilePath())
            qfile.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text)
            encodedData = qfile.readAll()
            fh = self.data(index, QtCore.Qt.DisplayRole)
            mimedata.setData("text/plain", encodedData)
            mimedata.setUrls([QtCore.QUrl.fromLocalFile(QtCore.QFileInfo(self.data(index, QtCore.Qt.DisplayRole)).absoluteFilePath())])
            qfile.close()

        return mimedata
