# -*- coding: utf-8 -*-
import os
import sys

from PyQt5 import QtWidgets, QtGui, QtCore

from search_machine import SearchMachine
from torrent_window import TorrentWidget


def main():
    app = QtWidgets.QApplication(sys.argv)
    # 搜尋 py檔案所在的目錄內的 icon 檔案
    app.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'search-website-512.png')))

    search_vm = SearchMachine()
    widget = TorrentWidget(parent=app, result=search_vm.result, signal_refresh=search_vm.signal_refresh,
                           signal_searching_keyword=search_vm.signal_searching_keyword)
    search_vm.signal_update_label = widget.signal_update_label
    search_vm.signal_update_window_title = widget.signal_update_window_title
    search_vm.start()

    model = QtGui.QStandardItemModel()
    #model.setHorizontalHeaderItem(0, QtGui.QStandardItem("title"))
    widget.table.setModel(model)
    widget.signal_refresh = search_vm.signal_refresh
    widget.table.horizontalHeader().hide()
    widget.thread().setObjectName('main thread')

    widget.signal_connect()
    search_vm.signal_searching_keyword.emit('', 1)

    widget.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
