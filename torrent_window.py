from datetime import datetime

from PyQt5 import QtCore, QtWidgets, QtGui
import queue

from bs4 import Tag


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
        self.table.pressed.connect(lambda index: self.on_table_pressed(index=index))
        self.lineeditor.returnPressed.connect(self.on_line_editor_return_press)
        self.signal_Searching_Finished.connect(self.on_refresh_tableview)
        self.signal_Update_Label.connect(lambda msg: self.status_label.setText(msg))
        self.table.doubleClicked.connect(lambda index: self.on_table_double_click(index))
        self.btn_nextpage.clicked.connect(lambda: self.on_change_page('next'))
        self.btn_prevpage.clicked.connect(lambda: self.on_change_page('prev'))
        self.signal_Update_Window_Title.connect(lambda msg: self.setWindowTitle('Torrent Browser Page[' + msg + ']'))

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
                    model.setData(item.index(), QtGui.QBrush(QtCore.Qt.red), QtCore.Qt.ForegroundRole)

                if seed_object.seed_num < 10 and seed_object.seed_num >2:
                    model.setData(item.index(), QtGui.QBrush(QtCore.Qt.darkGreen), QtCore.Qt.ForegroundRole)

                if seed_object.seed_num <= 2:
                    model.setData(item.index(), QtGui.QBrush(QtCore.Qt.darkYellow), QtCore.Qt.ForegroundRole)

            except AttributeError as e:
                print(seed_object, e)
                continue

        self.result.task_done()

        self.seeds_list = seeds_list
        self.table.setModel(model)
        self.table.scrollToTop()
        self.table.selectRow(0)

"""
    @QtCore.pyqtSlot(object)
    def on_table_pressed(self, index: QtCore.QModelIndex):
        model = self.table.model()
        threading.Thread(target=PageShell_Sukebei.seed_content,
                         args=(self.seeds_list[model.itemFromIndex(index).row()], self.result, self.signal_Update_Label)).start()
"""