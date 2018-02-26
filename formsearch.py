# -*- coding: utf-8 -*-
import os, sys, logging
from PyQt5 import QtCore, QtGui, QtWidgets


class TblWidget(QtWidgets.QTableWidget):
    def __init__(self, row, col):
        super().__init__(row, col)
        self.currentItemChanged.connect(self.fnRevPathStyle)

    def fnRevPathStyle(self, currentitem, previtem=None):
        if currentitem != None:
            currentitem.setText(QtCore.QDir().fromNativeSeparators(currentitem.text()))

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if not self.itemAt(event.pos()):
            self.insertRow(self.rowCount())
            self.openPersistentEditor(self.item(self.rowCount(), 1))

    def keyReleaseEvent(self, keyevent):
        self.fnRevPathStyle(self.currentItem())
        if keyevent.key() == QtCore.Qt.Key_Delete:
            self.removeRow(self.currentRow())


class TreeView(QtWidgets.QTreeView):
    def __init__(self):
        super().__init__()

        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        logging.debug('Drag - ' + event.mimeData().text())
        event.acceptProposedAction()
        data = QtGui.QDrag(self)
        data.setMimeData(event.mimeData())

    def dropEvent(self, event):
        logging.debug('Drop - ' + event.mimeData().text())
        #logging.debug('Widget ID - ' + event.source().effectiveWinId().__hex__())
        event.acceptProposedAction()

        data = QtGui.QDrag(self)
        data.setMimeData(event.mimeData())
        data.start(QtCore.Qt.CopyAction)

    def startDrag(self, *args, **kwargs):
        logging.debug('StartDrag - ')
        super(TreeView, self).startDrag(*args, **kwargs)


class Ui_Form(QtCore.QObject):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.setMinimumSize(600, 400)
        cssStyle="""QPushButton, QLineEdit {
                font-size:16px;
                border: 2px solid #8f8f91; border-width:1px; border-radius:8px; border-style: solid;
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde);
                min-height:24px; }

                QPushButton:pressed {
                    border: 2px solid #c0c0c0;
                }
                """
        path = os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'icon.ico')

        self.gridLayoutWidget = Form
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayoutWidget.setWindowIcon(QtGui.QIcon(path))

        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.gridLayoutWidget.setStyleSheet("background-color: #D8D8D8;")

        self.btnSearch = QtWidgets.QPushButton()
        self.btnSearch.setObjectName("btnSearch")
        self.btnSearch.setStyleSheet(cssStyle)

        self.strKeyWord = QtWidgets.QLineEdit()
        self.strKeyWord.setObjectName("revPath")
        self.strKeyWord.setStyleSheet(cssStyle)

        self.btnSave = QtWidgets.QPushButton()
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setStyleSheet(cssStyle)
        self.treeView = TreeView()
        self.treeView.setObjectName("treeView")
        self.treeView.setStyleSheet("font-size:16px;")

        self.tableWidget = TblWidget(0, 1)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setStyleSheet("font-size:16px;")
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tableWidget.setHorizontalHeaderLabels(['搜尋目錄'])
        #self.tableWidget.setSizePolicy()

        self.gridLayout.addWidget(self.strKeyWord,  0,  0, 1, 16)
        self.gridLayout.addWidget(self.btnSearch,   0, 16, 1, 2)
        self.gridLayout.addWidget(self.btnSave,     0, 18, 1, 2)
        self.gridLayout.addWidget(self.treeView,    1,  0, 9, 15)
        self.gridLayout.addWidget(self.tableWidget, 1, 15, 9, 5)

        self.gridLayoutWidget.setLayout(self.gridLayout)
        Form.setWindowTitle("多重目錄搜尋")
        self.btnSearch.setText("搜尋")
        self.btnSave.setText("儲存")

        QtCore.QMetaObject.connectSlotsByName(Form)
