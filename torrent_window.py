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


