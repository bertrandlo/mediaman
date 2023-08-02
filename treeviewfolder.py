import logging

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt

from utils import keyword_extract


class TreeViewFolder(QtWidgets.QTreeView):

    def __init__(self, parent):
        """
         當 treeview widget 與 QFilesystemModel 連結後 只需要設定
            setDragDropMode, setDragEnabled, setAcceptDrops, setDropIndicatorShown, setDefaultDropAction
            剩下的 treeview 會自己處理 dropEvent dragEnterEvent
            但使用者如果自行需要修改 這兩個事件 必須利用 super(userClassName, self).dropEvent(event)
            讓原本的自動動作執行而非直接覆寫這些事件處理函數
        :param parent:
        :return:
        """
        super().__init__()
        self.parent = parent

        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditKeyPressed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setSelectionMode(self.ExtendedSelection)
        self.customContextMenuRequested.connect(self.customCxMenuEvent)

    def dragEnterEvent(self, event):
        logging.debug('Drag - ' + event.mimeData().text())
        if 'application/x-qt-windows-mime;value="FileName"' in event.mimeData().formats():
            event.acceptProposedAction()
            super().dragEnterEvent(event)   # 呼叫父類別方法
        else:                               # 純文字的拖入處理
            if 'text/plain' in event.mimeData().formats():
                self.setAcceptDrops(True)
                QtWidgets.QApplication.clipboard().setText(event.mimeData().text())
                logging.debug('Drag Enter')
                event.accept()

    def dragMoveEvent(self, event):
        # logging.debug('Drag - ' + event.mimeData().text())
        if 'application/x-qt-windows-mime;value="FileName"' in event.mimeData().formats():
            event.acceptProposedAction()
            super().dragMoveEvent(event)   # 呼叫父類別方法
        else:                               # 純文字的拖入處理
            if 'text/plain' in event.mimeData().formats():
                event.accept()

    def dropEvent(self, event):
        logging.debug('Drop - ' + event.mimeData().text())
        if 'application/x-qt-windows-mime;value="FileName"' in event.mimeData().formats():
            super().dropEvent(event)
        else:
            idx = self.indexAt(self.viewport().mapFromGlobal(QtGui.QCursor.pos()))
            fn = self.model().fileName(idx)

            if fn == '':  # 檢查是否有點選在項目上才顯示選單
                msgbox = QtWidgets.QMessageBox(icon=QtWidgets.QMessageBox.Warning, text='請指定正確目錄')
                msgbox.setWindowFlags(Qt.Popup)
                msgbox.exec()
            else:
                QtWidgets.QApplication.clipboard().setText(event.mimeData().text())
                strNewName = fnRename(fn, event.mimeData().text())
                if strNewName != fn:
                    result = QtCore.QDir().rename(self.model().fileInfo(idx).dir().absoluteFilePath(fn),
                                           self.model().fileInfo(idx).dir().absoluteFilePath(strNewName))
                    if result:
                        self.parent.labelMsg.setText('[OK] ' + self.model().fileInfo(idx).dir().absoluteFilePath(strNewName))
                    else:
                        self.parent.labelMsg.setText('[Fail] ' + self.model().fileInfo(idx).dir().absoluteFilePath(strNewName))

                event.acceptProposedAction()

    def customCxMenuEvent(self, pos): # 右鍵選單 - TreeView Widget
        # 檢查是否有點選在項目上才顯示選單
        if self.model().fileName(self.indexAt(self.viewport().mapFromGlobal(QtGui.QCursor.pos()))) == '':
            return

        cxmenu = QtWidgets.QMenu()
        act1 = QtWidgets.QAction('整理', self)
        cxmenu.addAction(act1)
        action = cxmenu.exec_(self.viewport().mapToGlobal(pos))

        if action == act1:
            selDirFileinfo = self.model().fileInfo(self.currentIndex())
            fnOriginal = self.model().fileName(self.currentIndex())
            newFileName = fnRename(fnOriginal)

            if(len(QtGui.QGuiApplication.clipboard().text()) > 0):
                newFileName = QtGui.QGuiApplication.clipboard().text() + '_' + newFileName

            if fnOriginal != newFileName:
                new_file_name = selDirFileinfo.dir().absoluteFilePath(newFileName)
                result = QtCore.QDir().rename(selDirFileinfo.dir().absoluteFilePath(fnOriginal), new_file_name)
                if result:
                    self.parent.labelMsg.setText('[OK] '+selDirFileinfo.dir().absoluteFilePath(newFileName))
                else:
                    QtCore.QDir().rename(selDirFileinfo.dir().absoluteFilePath(fnOriginal), new_file_name + '_[重複]')
                    self.parent.labelMsg.setText('[Fail] '+selDirFileinfo.dir().absoluteFilePath(newFileName))


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