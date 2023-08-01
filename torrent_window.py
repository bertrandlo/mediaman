from datetime import datetime

from PyQt5 import QtCore, QtWidgets, QtGui
import queue

from bs4 import Tag

from search_machine import SearchMachine, Linker


class ClickLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mouseDoubleClickEvent(self, *args, **kwargs):
        if len(self.parent().table.selectedIndexes()) > 0:
            idx = self.parent().table.selectedIndexes()[0]
            #print(self.parent().seeds_list[idx.row()].content_link)
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.parent().seeds_list[idx.row()].content_link))


class MyTableView(QtWidgets.QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == QtCore.Qt.Key_Left:
            self.parent().on_Change_Page('prev')
            return

        if QKeyEvent.key() == QtCore.Qt.Key_Right:
            self.parent().on_Change_Page('next')
            return
        """
        if QKeyEvent.key() == QtCore.Qt.Key_Return:
            if len(self.parent().table.selectedIndexes()) > 0:
                idx = self.parent().table.selectedIndexes()[0]
                # print(self.parent().seeds_list[idx.row()].content_link)
                threading.Thread(target=QtGui.QDesktopServices.openUrl,
                                 args=(QtCore.QUrl(self.parent().seeds_list[idx.row()].content_link),)).start()

                return
        """
        super().keyPressEvent(QKeyEvent)


class TorrentWidget(QtWidgets.QWidget):

    signal_update_label = QtCore.pyqtSignal(str)
    signal_update_window_title = QtCore.pyqtSignal(str)
    signal_refresh = None
    signal_Searching_Keyword = None
    result: queue = None

    def __init__(self, parent: QtWidgets.QApplication, result: queue, signal_refresh: QtCore.pyqtSignal,
                 signal_searching_keyword: QtCore.pyqtSignal, **kwargs):
        self.signal_searching_keyword = signal_searching_keyword
        self.signal_refresh = signal_refresh
        super().__init__()
        self.seeds_list = []
        self.result = result
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
        self.table = MyTableView(self)
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
        self.signal_refresh.connect(self.on_refresh_tableview)
        self.table.pressed.connect(lambda index: self.on_table_pressed(index=index))
        self.lineeditor.returnPressed.connect(self.on_line_editor_return_press)
        self.signal_update_window_title.connect(lambda msg: self.status_label.setText(msg))
        self.table.doubleClicked.connect(lambda index: self.on_table_double_click(index))
        self.btn_nextpage.clicked.connect(lambda: self.on_change_page('next'))
        self.btn_prevpage.clicked.connect(lambda: self.on_change_page('prev'))
        self.signal_update_window_title.connect(lambda msg: self.setWindowTitle('Torrent Browser Page[' + msg + ']'))

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == QtCore.Qt.Key_Escape:
            self.showMinimized()

    def on_change_page(self, action):
        if action == 'prev':
            self.signal_Page_Change.emit(-1)
        if action == 'next':
            self.signal_Page_Change.emit(1)

    @QtCore.pyqtSlot(object)
    def on_table_double_click(self, index: QtCore.QModelIndex):
        download_link = (self.seeds_list[self.table.model().itemFromIndex(index).row()]).download_link
        print(download_link)
        self.signal_Download_Torrent.emit(download_link)

        #keyword_extract(item[0])

    def on_line_editor_return_press(self):
        self.signal_Searching_Keyword.emit(self.lineeditor.text().strip(), 0)

    @QtCore.pyqtSlot()
    def on_refresh_tableview(self):
        print("self.result =>{}".format(len(self.result.queue)))
        if self.result is None or len(self.result.queue) == 0:
            return

        model = QtGui.QStandardItemModel()
        #model.clear()
        seeds_list = []

        for linker in list(self.result.queue):
            print(linker)
            try:
                #print(str(seed_object.seed_num), seed_object.size, seed_object.title)
                item = QtGui.QStandardItem(' [S: '+str(linker.seed_count)+'] ' + '['+linker.size+']' + str(linker.title))
            except AttributeError as e:
                print(e, linker, type(linker))
                continue

            model.appendRow([item])
            seeds_list.append(linker)

            try:
                if linker.seed_count >= 20:
                    model.setData(item.index(), QtGui.QBrush(QtCore.Qt.red), QtCore.Qt.ForegroundRole)

                if 10 > linker.seed_count > 2:
                    model.setData(item.index(), QtGui.QBrush(QtCore.Qt.darkGreen), QtCore.Qt.ForegroundRole)

                if linker.seed_count <= 2:
                    model.setData(item.index(), QtGui.QBrush(QtCore.Qt.darkYellow), QtCore.Qt.ForegroundRole)

            except AttributeError as e:
                print(linker, e)
                continue

        self.result.task_done()

        self.seeds_list = seeds_list
        self.table.setModel(model)
        self.table.scrollToTop()
        self.table.selectRow(0)

    @QtCore.pyqtSlot(object)
    def on_table_pressed(self, index: QtCore.QModelIndex):
        return
