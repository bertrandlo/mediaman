# -*- coding: utf-8 -*-
# 處理所有硬碟影片檔案索引
# 規劃設計了一個 CoreMachine 類別處理所有的工作 UI Singal Connect 交待工作
import os
import sys
import logging
import sqlite3
import datetime
import itertools
import threading
import queue
import time
import copy
from PyQt5 import QtCore, QtGui, QtWidgets

import tree

db_location = 'files.db'
disk_set = []

def GetHumanReadable(size, precision=1):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    if size is not None:
        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1 #increment the index of the suffix
            size = size/1024.0 #apply the division
        return "%.*f%s" % (precision,size,suffixes[suffixIndex])
    else:
        return 'No File Size Data'


def scan_directory(semaphore: threading.Semaphore, sql_cmd_queue: queue.Queue, label, signal_JobFinished = None):
    semaphore.acquire()
    conn = sqlite3.connect(db_location)
    cur = conn.cursor()
    exclude_prefixes = ['$RECYCLE.BIN']

    if len(cur.execute("SELECT * FROM disk WHERE label = ?", [label]).fetchall()) > 0:
        disk_info = cur.execute("SELECT * FROM disk WHERE label = ?", [label]).fetchall()[0]
        disk_id = disk_info[0]
        scan_path = disk_info[2]

    # 清除相同 disk_id 的紀錄
    sql_cmd_queue.put(("DELETE FROM files WHERE disk_id = ?", (copy.copy(disk_id),)))
    count = 0
    for root, dirs, files in os.walk(scan_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude_prefixes]
        # print("{} - {} consumes {} bytes".format(files_count, root, sum(getsize(join(root, name)) for name in files)))
        # if len(files) > 0:
        for filename in files:

            try:
                file_size = os.stat(os.path.join(root, filename)).st_size    # in bytes
            except FileNotFoundError:
                continue
            except OSError as e:  # 有問題的檔名或目錄名稱 --> 不處理
                print(e)
                continue

            sql_cmd_queue.put(("INSERT INTO files VALUES (?, ?, ?, ?)", (root, filename, disk_id, file_size)), block=False)
            count += 1

        if len(files) == 0:    # 目錄 - 將檔名欄位空白
            #print(root, disk_id)
            sql_cmd_queue.put(("INSERT INTO files VALUES (?, ?, ?, ?)", (root, '', disk_id, 0)))
            count += 1

    sql_cmd_queue.put(("COMMIT",), block=False)
    print("Files Count = " + str(count))

    space_available = GetHumanReadable(QtCore.QStorageInfo(scan_path).bytesAvailable()) + '/' + \
        GetHumanReadable(QtCore.QStorageInfo(scan_path).bytesTotal())
    print(label + " - Available Space = " + space_available)
    check_date = datetime.datetime.now().strftime("%Y%m%d %H%M%S")
    sql_cmd_queue.put(("UPDATE disk SET space_available = ? , check_date = ? WHERE disk_id = ?", copy.copy((space_available, check_date, disk_id))))

    print(label + " os.walk() Finished")
    signal_JobFinished.emit(label + " os.walk() Finished")
    semaphore.release()


class SQLExecuter(QtCore.QObject):

    signal_Exit = QtCore.pyqtSignal()

    def __init__(self, sql_cmd_queue: queue.Queue):
        '''
        專處理 刪除與修改 利用 queue 避免資料庫鎖定
        :param sql_cmd_queue: 要執行的 SQL 敘述
        '''
        super().__init__()
        self.sql_cmd_queue = sql_cmd_queue
        self.flag_exit = False
        self.signal_Exit.connect(self.exitproc)
        self.lock = threading.Lock()

    @QtCore.pyqtSlot()
    def exitproc(self):
        with self.lock:
            self.flag_exit = True

    def wait(self):
        conn = sqlite3.connect(db_location)
        cur = conn.cursor()
        count = 0

        while not self.flag_exit:
            try:
                cmd = self.sql_cmd_queue.get(block=True, timeout=0.01)
                if cmd[0] == 'COMMIT':
                    conn.commit()
                else:
                    cur.execute(cmd[0], cmd[1])
                    count += 1
            except queue.Empty:
                QtWidgets.QApplication.processEvents()

        print("EXIT SQL Command Count = " + str(count))
        cur.close()
        conn.close()


class TblWidget(QtWidgets.QTableWidget):

    signal_Update_LabelMsg = None
    signal_LoadSearchPath = QtCore.pyqtSignal()
    signal_Update_Disk_Files = None

    def __init__(self, row, col):
        super().__init__(row, col)
        self.update_disk_timer = QtCore.QTimer()
        self.update_disk_timer.start(3000)
        #self.currentItemChanged.connect(self.fnRevPathStyle)
        #self.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.conn = None
        self.label_msg = ''
        self.cellClicked.connect(lambda row, column: self.cellclicked(row, column))
        self.cellDoubleClicked.connect(lambda row, column: self.celldoubleclicked(row, column))
        self.itemDelegate().closeEditor.connect(self.fnSaveSearchPath)
        self.flag_Update = False    # 避免更新引起的 rowAboutToBeRemoved()

        self.update_disk_timer.timeout.connect(self.fnUpdateDiskConnectionStatus)

    def signal_connect(self):
        self.signal_LoadSearchPath.connect(self.fnLoadSearchPath, QtCore.Qt.QueuedConnection)

    def rowsAboutToBeRemoved(self, index, start, end):
        if self.flag_Update:
            return
        #print(index, start, end)
        disk_id = self.item(start, 2).text()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM files WHERE disk_id = ?", [disk_id])
        cur.execute("DELETE FROM disk WHERE disk_id = ?", [disk_id])
        cur.execute("VACUUM files")
        self.conn.commit()

    @QtCore.pyqtSlot()
    def fnUpdateDiskConnectionStatus(self):
        for idx in range(self.rowCount()):
            item = QtCore.QStorageInfo(self.item(idx, 1).text())
            if not(item.isValid() and item.isReady()):
                self.item(idx, 0).setForeground(QtGui.QBrush(QtCore.Qt.darkRed))
                self.item(idx, 1).setForeground(QtGui.QBrush(QtCore.Qt.black))
            else:
                self.item(idx, 1).setForeground(QtGui.QBrush(QtCore.Qt.gray))

    @QtCore.pyqtSlot()
    def fnLoadSearchPath(self):
        self.flag_Update = True
        selected_row = -1
        if len(self.selectedItems()) > 0:
            selected_row = (self.selectedItems()[0]).row()

        row_count = self.rowCount()
        self.model().removeRows(0, row_count)
        cur = self.conn.cursor()
        idx = 0
        for row in cur.execute("SELECT * FROM disk ORDER BY disk_id"):
            self.insertRow(self.rowCount())
            #print(row)
            try:
                self.setItem(idx, 2, QtWidgets.QTableWidgetItem(str(row[0]), 0))    # disk_id (integral)
                self.setItem(idx, 0, QtWidgets.QTableWidgetItem(row[1], 0))         # label
                self.setItem(idx, 1, QtWidgets.QTableWidgetItem(row[2], 0))         # path
                if not (QtCore.QStorageInfo(QtWidgets.QTableWidgetItem(row[2], 0).text()).isValid() and
                        QtCore.QStorageInfo(QtWidgets.QTableWidgetItem(row[2], 0).text()).isReady()):
                    self.item(idx, 1).setForeground(QtGui.QBrush(QtCore.Qt.gray))
                self.setItem(idx, 3, QtWidgets.QTableWidgetItem(row[3], 0))         # volume space
                self.setItem(idx, 4, QtWidgets.QTableWidgetItem(row[4], 0))         # check date
            except TypeError as e:
                print(e)
                pass
            idx += 1
        self.flag_Update = False

        if selected_row != -1:
            self.selectRow(selected_row)

    def fnSaveSearchPath(self):
        cur = self.conn.cursor()
        #pathset = cur.execute("SELECT * FROM disk ORDER BY disk_id ASC").fetchall()
        for idx in range(self.rowCount()):
            disk_id = str(self.item(idx, 2).text())
            if disk_id != "":  # 存在同樣 disk_id 紀錄
                pathset = cur.execute("SELECT * FROM disk WHERE disk_id = ?", [disk_id]).fetchall()
                if len(pathset) == 0:
                    print("No mathcing disk_id", disk_id)
                    return

                if pathset[0][1] != self.item(idx, 0).text():
                    #print(str(self.item(idx, 0).text()), str(self.item(idx, 1).text()), idx)
                    cur.execute("UPDATE disk SET label = ? WHERE disk_id = ?",
                                [self.item(idx, 0).text(),  self.item(idx, 2).text()])
                    self.conn.commit()
                if pathset[0][2] != self.item(idx, 1).text():
                    # 修改路徑資訊
                    cur.execute("UPDATE disk SET path = ? WHERE disk_id = ?",
                                [self.item(idx, 1).text(),  self.item(idx, 2).text()])
                    self.conn.commit()
                    print('signal_Update_Disk_Files', self.item(idx, 0).text())
                    self.signal_Update_Disk_Files.emit([self.item(idx, 0).text()])

                    info = cur.execute('SELECT * FROM disk WHERE disk_id = ?', [self.item(idx, 2).text()]).fetchone()
                    self.setItem(idx, 3, QtWidgets.QTableWidgetItem(info[3], 0))
                    self.setItem(idx, 4, QtWidgets.QTableWidgetItem(info[4], 0))
            else:
                cur.execute("INSERT INTO disk (label, path) VALUES (?, ?)",
                            [self.item(idx, 0).text(), self.item(idx, 1).text()])
                self.conn.commit()
                new_id = cur.execute('SELECT max(disk_id) FROM disk').fetchone()[0]
                self.setItem(idx, 2, QtWidgets.QTableWidgetItem(str(new_id), 0))

    def mouseDoubleClickEvent(self, qevent: QtGui.QMouseEvent):
        if self.itemAt(qevent.pos()) is not None:
            print(self.itemAt(qevent.pos()).text())
            super().mouseDoubleClickEvent(qevent)
        else:
            cnt = self.rowCount()
            self.insertRow(self.rowCount())
            for idx in range(self.columnCount()):
                self.setItem(cnt, idx, QtWidgets.QTableWidgetItem("", 0))

            self.edit(self.indexFromItem(self.item(cnt, 0)))

    def fnRevPathStyle(self, currentitem, previtem=None):
        if currentitem != None:
            currentitem.setText(QtCore.QDir().fromNativeSeparators(currentitem.text()))

    def cellclicked(self, row, column):
        self.selectRow(row)
        self.label_msg = self.item(row, 0).text() + ' - ' + self.item(row, 3).text() + '@' + self.item(row, 4).text()
        self.signal_Update_LabelMsg.emit(self.label_msg)

    def celldoubleclicked(self, row, column):
        if column == 1:
            dlg = QtWidgets.QFileDialog()
            dlg.setFileMode(QtWidgets.QFileDialog.DirectoryOnly)
            if dlg.exec_():
                self.item(row, column).setText(dlg.selectedFiles()[0])
        else:
            self.edit(self.indexFromItem(self.item(row, column)))

    def keyReleaseEvent(self, keyevent):
        self.fnRevPathStyle(self.currentItem())
        if keyevent.key() == QtCore.Qt.Key_Delete:
            self.removeRow(self.currentRow())


class MessageLabel(QtWidgets.QLabel):
    signal_MessageLabel_Busy = QtCore.pyqtSignal(bool)
    def __init__(self):
        super().__init__()
        self.timer = QtCore.QTimer()
        self.busy_msg = itertools.cycle(". .. ... .... ..... ......".split(" "))
        self.signal_MessageLabel_Busy.connect(self.busy_state)
        self.msg = ''
        self.timer.timeout.connect(self.update_msg)

    @QtCore.pyqtSlot(bool)
    def busy_state(self, busy_state: bool):
        if busy_state:
            self.msg = ""
            self.timer.start(300)
        else:
            self.timer.stop()
            self.setText(self.msg)

    def update_msg(self):
        self.setText(self.msg + next(self.busy_msg))


class Ui_Form(QtCore.QObject):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.setMinimumSize(600, 400)


        cssStyle = """
                QWidget {
                    font-size:16px;
                    color: #aaa;
                    border: 2px solid; 
                    border-width:1px; 
                    border-style: solid;
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #222, stop: 1 #333);
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
                    background-color: #555555;
                }
                """

        path = os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'Files-icon.png')

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
        self.treeView = tree.TreeView()
        self.treeView.setObjectName("treeView")
        self.treeView.setStyleSheet(cssStyle)

        self.tableWidget = TblWidget(0, 5)
        self.tableWidget.hideColumn(2)                  # 儲存 disk_id
        self.tableWidget.hideColumn(3)
        self.tableWidget.hideColumn(4)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setStyleSheet(cssStyle)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tableWidget.setHorizontalHeaderLabels(['Lable', 'Path'])
        #self.tableWidget.setSizePolicy()

        self.labelMsg = MessageLabel()
        self.labelMsg.setStyleSheet(cssStyle)

        self.gridLayout.addWidget(self.strKeyWord,  0,  0, 1, 16)
        self.gridLayout.addWidget(self.btnSearch,   0, 16, 1, 2)
        self.gridLayout.addWidget(self.btnSave,     0, 18, 1, 2)
        self.gridLayout.addWidget(self.treeView,    1,  0, 28, 15)
        self.gridLayout.addWidget(self.tableWidget, 1, 15, 29, 5)
        self.gridLayout.addWidget(self.labelMsg,    29,  0, 1, 15)

        self.gridLayoutWidget.setLayout(self.gridLayout)
        Form.setWindowTitle("目錄檔案資料庫")
        self.btnSearch.setText("搜尋")
        self.btnSave.setText("更新")

        self.strKeyWord.returnPressed.connect(self.btnSearch.click)

        QtCore.QMetaObject.connectSlotsByName(Form)


class CoreMachine(QtCore.QObject):

    signal_Exit = QtCore.pyqtSignal()
    signal_JobFinished = QtCore.pyqtSignal(str)
    signal_Update_Disk_Files = QtCore.pyqtSignal(list)

    signal_MessageLabel_Busy = None
    signal_Update_LabelMsg = None
    signal_LoadSearchPath = None
    flag_Busy = False

    def __init__(self, conn):
        super().__init__()
        self.count = 0
        self.timer = QtCore.QTimer()
        self.busy_msg = itertools.cycle(". .. ... .... ..... ......".split(" "))
        self.msg = ""
        self.mounted_disks_number = len(QtCore.QStorageInfo.mountedVolumes())
        self.conn = conn
        self.max_thread = 6

        self.entire_path_set = None
        self.lock = threading.Lock()

        self.signal_JobFinished.connect(self.job_finished, QtCore.Qt.QueuedConnection)

    def signal_connect(self):
        self.signal_Update_Disk_Files.connect(self.scan_disk, QtCore.Qt.QueuedConnection)

    def run(self):
        print('StateMachine @ ' + QtCore.QThread.currentThread().objectName())
        self.timer.timeout.connect(self.tick)
        self.timer.start(200)

    def set_path_set(self, pathset):
        with self.lock:
            self.entire_path_set = pathset

    @QtCore.pyqtSlot(str)
    def job_finished(self, msg):
        self.signal_Update_LabelMsg.emit(msg)
        QtWidgets.QApplication.processEvents()

    @QtCore.pyqtSlot(list)
    def scan_disk(self, path_set):
        self.flag_Busy = True
        self.signal_MessageLabel_Busy.emit(True)
        print("scan_disk @ {}".format(QtCore.QThread.currentThread().objectName()))
        self.signal_LoadSearchPath.emit()
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        semaphore = threading.Semaphore(value=self.max_thread)
        sql_cmd_queue = queue.Queue(maxsize=-1)
        sql_cmd_executor = SQLExecuter(sql_cmd_queue)

        threads = []
        thread_sqlcmdexecutor = threading.Thread(target=sql_cmd_executor.wait)
        thread_sqlcmdexecutor.start()

        for job in path_set:
            threads.append(threading.Thread(target=scan_directory, kwargs={"semaphore": semaphore, "sql_cmd_queue": sql_cmd_queue,
                                                                           "label": job, "signal_JobFinished": self.signal_JobFinished}))
            threads[-1].start()

        for th in threads:
            while th.is_alive():
                th.join(timeout=0.05)
                QtWidgets.QApplication.processEvents()

        while not sql_cmd_queue.empty():                    # 等待 sql command queue 清空
            QtWidgets.QApplication.processEvents()

        sql_cmd_executor.signal_Exit.emit()
        QtWidgets.QApplication.processEvents()
        thread_sqlcmdexecutor.join()

        conn = sqlite3.connect(db_location)
        cur = conn.cursor()
        cur.execute('VACUUM files')
        conn.commit()

        QtWidgets.QApplication.restoreOverrideCursor()
        self.flag_Busy = False
        self.signal_MessageLabel_Busy.emit(False)
        self.signal_Update_LabelMsg.emit("Scanning Job Finished")

    def tick(self):
        QtWidgets.QApplication.processEvents()


class searchWidget(QtWidgets.QWidget):

    signal_Update_LabelMsg = QtCore.pyqtSignal(str)
    signal_Searching = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QApplication):
        super().__init__()
        self.settings = QtCore.QSettings("candy", "brt")
        self.conn = sqlite3.connect(db_location)

        #self.treemodel = QtGui.QStandardItemModel()
        self.treemodel = tree.TreeModel(conn=self.conn)

        self.parent = parent
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        #self.settings = parent.settings
        self.ui.treeView.setModel(self.treemodel)
        self.ui.treeView.signal_Searching = self.signal_Searching
        self.threadPool = []

        #載入預設搜尋點
        self.ui.tableWidget.conn = self.conn
        self.ui.tableWidget.fnLoadSearchPath()

        # signal pass
        self.ui.tableWidget.signal_Update_LabelMsg = self.signal_Update_LabelMsg
        self.move(self.settings.value("search-win-pos", QtCore.QPoint(100, 100)))
        self.resize(QtCore.QSize(900, 600))

        # 不能省掉前面的 self 宣告 否則物件會在 init 後  因為會沒有被參照 會被自動刪除回收
        self.thread_tick = QtCore.QThread(objectName='thread_Tick')
        self.thread_tick.start()
        self.cm1 = CoreMachine(conn=self.conn)
        self.cm1.signal_Update_LabelMsg = self.signal_Update_LabelMsg
        self.cm1.signal_LoadSearchPath = self.ui.tableWidget.signal_LoadSearchPath
        self.cm1.signal_MessageLabel_Busy = self.ui.labelMsg.signal_MessageLabel_Busy
        self.cm1.signal_connect()
        self.cm1.moveToThread(self.thread_tick)
        self.cm1.run()

        self.ui.tableWidget.signal_Update_Disk_Files = self.cm1.signal_Update_Disk_Files
        self.ui.tableWidget.signal_connect()

        self.signal_Update_LabelMsg.connect(self.update_labelmsg)
        self.signal_Searching.connect(self.fnSearching)
        self.ui.btnSave.clicked.connect(self.fnUpdating)
        self.ui.btnSearch.clicked.connect(self.fnSearching)
        self.ui.treeView.doubleClicked.connect(self.treedbclick)
        self.ui.treeView.signal_item_clicked.connect(lambda idx: self.update_labelmsg(
            GetHumanReadable(self.treemodel.itemFromIndex(idx).file_size)))

    @QtCore.pyqtSlot(str)
    def update_labelmsg(self, msg):
        self.cm1.msg = msg
        self.ui.labelMsg.setText(msg)

    def fnSearching(self):
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        self.ui.treeView.model().clear()
        keyword = self.ui.strKeyWord.text().strip().split()
        if len(keyword) == 0:
            QtWidgets.QApplication.restoreOverrideCursor()
            return
        cur = self.conn.cursor()
        disk_id_dict = {}
        for idx in range(self.ui.tableWidget.rowCount()):
            disk_id = self.ui.tableWidget.item(idx, 2).text()
            disk_id_dict[disk_id] = tree.treeitem(self.ui.tableWidget.item(idx, 1).text())
            disk_id_dict[disk_id].label = self.ui.tableWidget.item(idx, 0).text()
            disk_id_dict[disk_id].setText(disk_id_dict[disk_id].label)
            disk_id_dict[disk_id].disk_id = self.ui.tableWidget.item(idx, 2).text()
            disk_id_dict[disk_id].count = 0
            disk_id_dict[disk_id].file_size = 0
            self.ui.treeView.model().appendRow(disk_id_dict[disk_id])
        sql_cmd = 'SELECT *, ROWID FROM files WHERE '
        cmd_term = ' ( directory LIKE ? OR filename LIKE ? ) '
        idx = 0
        parameters = []
        for key_term in keyword:
            if idx > 0:
                sql_cmd += ' AND '
            sql_cmd += cmd_term
            parameters.append('%' + key_term + '%')
            parameters.append('%' + key_term + '%')
            idx += 1
        sql_cmd += ' ORDER BY directory ASC'
        print(sql_cmd)
        for item in cur.execute(sql_cmd, parameters).fetchall():
            #print(item[0], item[1], item[2])
            disk_id = str(item[2])
            disk_id_dict[disk_id].count += 1
            file_item = tree.treeitem(item[0] + QtCore.QDir.separator() + item[1])
            file_item.ROWID = item[4]
            file_item.file_size = item[3]  # in bytes
            disk_id_dict[disk_id].appendRow([file_item])
            disk_id_dict[disk_id].setText(disk_id_dict[disk_id].label)

            if disk_id_dict[disk_id].rowCount() <= 5:
                self.ui.treeView.setExpanded(disk_id_dict[disk_id].index(), True)
            else:
                self.ui.treeView.setExpanded(disk_id_dict[disk_id].index(), False)

        QtWidgets.QApplication.restoreOverrideCursor()

    def fnUpdating(self):  # 更新目錄資料庫的檔案名稱資料
        drive = []
        entire_disk_path = []

        for idx in range(self.ui.tableWidget.rowCount()):
            entire_disk_path.append(self.ui.tableWidget.item(idx, 1).text())

        self.cm1.entire_path_set = entire_disk_path

        if len(self.ui.tableWidget.selectedItems()) > 0:
            row = self.ui.tableWidget.selectedItems()[0].row()
            disk_path = self.ui.tableWidget.item(row, 1).text()
            disk_label = self.ui.tableWidget.item(row, 0).text()
            if QtCore.QStorageInfo(disk_path).isValid() and QtCore.QStorageInfo(disk_path).isReady():
                drive.append(disk_label)
        else:
            for idx in range(self.ui.tableWidget.rowCount()):
                disk_path = self.ui.tableWidget.item(idx, 1).text()
                disk_label = self.ui.tableWidget.item(idx, 0).text()
                if QtCore.QStorageInfo(disk_path).isValid() and QtCore.QStorageInfo(disk_path).isReady():
                    drive.append(disk_label)
        print(drive)

        self.cm1.scan_disk(drive)

    def treedbclick(self, idx):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl().fromLocalFile(self.ui.treeView.model().itemFromIndex(idx).qfileinfo.absolutePath()))

    def closeEvent(self, QMoveEvent):
        super(searchWidget, self).closeEvent(QMoveEvent)    #寫入需要儲存的參數
        self.settings.setValue("search-win-pos", self.pos())
        self.settings.sync()
        self.deleteLater()                                                #多個視窗 避免退出錯誤


def main():
    #logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QtWidgets.QApplication(sys.argv)
    QtCore.QThread.currentThread().setObjectName('Main')
    widget = searchWidget(app)
    widget.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()