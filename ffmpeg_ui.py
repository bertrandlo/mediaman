# -*- coding: utf-8 -*-
import os, sys, json, queue, io
import subprocess, pprint, re, time
import random, string, copy
import utils
from collections import deque
from threading import Thread
from utils import GetHumanReadable
from PyQt5 import QtCore, QtWidgets, QtGui

# ffmpeg.exe -i C:\Users\brt\Desktop\VBOX\IDOL-063.avi -c:v hevc_nvenc -crf 25 -preset slow -2pass 1  -rc-lookahead 32
# C:\Users\brt\Desktop\VBOX\test.mp4

class media(object):

    proc = None
    msg = None
    jobID = None
    pgwin = None    # 對應的 progress dialog ID
    fps = None
    qfactor = None
    kbps = None
    filesize = None

    def __init__(self, source_file, qp=25):
        '''
        需要ffmpeg子目錄下包含 ffprobe 工具程式
        :param source_file: file location 
        :param qp: ffmpeg comand option
        '''
        super().__init__()

        self.si = subprocess.STARTUPINFO()
        self.si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.pg = 0
        self.source_file = source_file
        self.source = QtCore.QFileInfo(source_file)
        self.model_item = QtGui.QStandardItem(self.source.fileName())
        self.probe_util = QtCore.QFileInfo(os.path.realpath(__file__)).absolutePath() + "/ffmpeg/bin/ffprobe.exe"
        self.qp = qp

        self.tags = {'format': ('duration', 'size', 'probe_score'),
                     'video': ('codec_name', 'profile', 'bit_rate', 'avg_frame_rate', 'nb_frames', 'width', 'height'),
                     'audio': ('codec_name', 'sample_rate')
                     }
        self.m = re.compile(r'time=[0-9]+[:][0-9]+[:][0-9]+')

        if not self.source.exists():
            raise FileNotFoundError

        proc = subprocess.Popen([self.probe_util, '-v', 'quiet', '-select_streams', 'v:0', '-show_format', '-show_streams',
                                 '-print_format', 'json', source_file],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=self.si)
        output, errors = proc.communicate()
        self.media_info = json.loads(output.decode('utf-8'))
        #self.model.setHorizontalHeaderItem(0, QtGui.QStandardItem(self.source.fileName()))

        path = QtGui.QStandardItem('FORMAT')
        for attr in self.tags['format']:
            if attr in self.media_info['format']:
                if attr == 'duration':
                    self.duration = int(float(self.media_info['format'][attr]))

                if attr == 'size':
                    path.appendRow(QtGui.QStandardItem(attr + ': ' + GetHumanReadable(int(self.media_info['format'][attr]))))
                else:
                    path.appendRow(QtGui.QStandardItem(attr + ': ' + str(self.media_info['format'][attr])))

        self.model_item.appendRow(path)

        streams_dict = {'format': [QtGui.QStandardItem(self.source.absolutePath())], 'video': [], 'audio': []}

        for stream in self.media_info['streams']:
            stream_item = QtGui.QStandardItem('stream')
            if stream['codec_type'] != 'video' and stream['codec_type'] != 'audio':
                continue
            for attr in self.tags[stream['codec_type']]:
                if attr in stream:
                    if attr == 'width' or attr == 'height':
                        setattr(self, attr, int(stream[attr]))

                    if attr == 'bit_rate':
                        stream_item.appendRow(QtGui.QStandardItem(str(attr) + ': ' + str(int(stream[attr])//(1024)) + 'kbps'))
                    else:
                        stream_item.appendRow(QtGui.QStandardItem(str(attr) + ': ' + str(stream[attr])))

            streams_dict[stream['codec_type']].append(stream_item)

        self.model_item.appendRow(self.list_stream(streams_dict['video'], QtGui.QStandardItem('VIDEO')))
        self.model_item.appendRow(self.list_stream(streams_dict['audio'], QtGui.QStandardItem('AUDIO')))
        #self.print()

    def __str__(self):
        return json.dumps(self.media_info, sort_keys=True, indent=4)

    def list_stream(self, stream_list, treeitem):
        idx = 1

        for item in stream_list:
            item.setText('#'+str(idx))
            treeitem.appendRow(item)
            idx += 1

        return treeitem

    @property
    def progress(self):

        line = self.msg.readline()
        if line:
            output = list(filter(None, re.split('\s+|=\s?', line))) # 移除串列 re.split('\s+|=\s?', line) 的空元素 ffmpeg output 的問題
            if output[0] == 'frame' and output[2] == 'fps':
                self.fps = output[3]
                self.qfactor = output[5]
                self.kbps = output[11]
                self.filesize = output[7]

                return int(int(output[1])/30), utils.GetHumanReadable(int(output[7][:-2])*1024)

        return None, None

    def print(self):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.media_info)

    def transcode(self, output_directory):

        output_file = QtCore.QDir.fromNativeSeparators(output_directory) + r'/' + self.source.completeBaseName()+'.mp4'
        chk_file_exist = QtCore.QFileInfo(output_file)

        postappendix = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(4)])
        output_file = QtCore.QDir.fromNativeSeparators(output_directory) + r'/' + self.source.completeBaseName() + \
            '-' + postappendix + '.mp4'


        self.proc = subprocess.Popen([QtCore.QFileInfo(os.path.realpath(__file__)).absolutePath() + "/ffmpeg/bin/ffmpeg.exe",
                                    '-hide_banner', '-y', '-hwaccel', 'cuvid', '-i', self.source_file, '-c:v', 'hevc_nvenc',
                                    '-preset', 'slow', '-rc', 'constqp', '-profile:v', 'main10', '-qp', str(self.qp),
                                    '-rc-lookahead', '32', output_file],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=self.si, bufsize=1024*4)

        self.msg = io.TextIOWrapper(self.proc.stdout, encoding="utf-8")

        return self.proc.stdin, self.proc.stdout


class ClickLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mouseDoubleClickEvent(self, *args, **kwargs):
        if len(self.parent().table.selectedIndexes()) > 0:
            idx = self.parent().table.selectedIndexes()[0]
            #print(self.parent().seeds_list[idx.row()].content_link)
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.parent().seeds_list[idx.row()].content_link))


class ProgWindow(QtWidgets.QProgressDialog):

    signal_ShowNormal = QtCore.pyqtSignal()
    signal_MoveDialog = QtCore.pyqtSignal()
    signal_Hide = QtCore.pyqtSignal()
    signal_Flag_Using_Set = QtCore.pyqtSignal(bool)

    def __init__(self, idx):
        super().__init__()
        self.idx = idx
        self.setStyleSheet(r'''
                    QProgressBar {
                    border: 1px solid black;
                    padding: 1px;
                    border-radius: 4px;
                    text-align: center;
                    background: QLinearGradient( x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #fff,
                    stop: 0.4999 #eee,
                    stop: 0.5 #ddd,
                    stop: 1 #eee );
                    }
                ''')
        self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'working.png')))
        self.setLabelText('Conversion Job')
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(100)

        self._flag_Using = False

        self.signal_ShowNormal.connect(self.showNormal)
        self.signal_MoveDialog.connect(self.moveDialog)
        self.signal_Hide.connect(self.showMinimized)
        self.signal_Flag_Using_Set.connect(lambda status: self.flag_Using_setter(status))

        self.scn = QtWidgets.QDesktopWidget()
        self.scnRect = self.scn.screenGeometry()

        if self.idx == 0:
            self.setGeometry(self.scnRect.width() - 240, self.scnRect.height() - 360, 200, 100)
        if self.idx == 1:
            self.setGeometry(self.scnRect.width() - 240, self.scnRect.height() - 220, 200, 100)

    @property
    def flag_Using(self):
        return self._flag_Using

    @QtCore.pyqtSlot(bool)
    def flag_Using_setter(self, status):
        self._flag_Using = status

    @flag_Using.setter
    def flag_Using(self, status):
        self._flag_Using = status

    @QtCore.pyqtSlot()
    def moveDialog(self):
        if self.idx == 0:
            self.setGeometry(self.scnRect.width() - self.width()-20, self.scnRect.height() - 360, self.width(), self.height())
        if self.idx == 1:
            self.setGeometry(self.scnRect.width() - self.width()-20, self.scnRect.height() - 220, self.width(), self.height())


class UIWidget(QtWidgets.QWidget):

    signal_Update_Treeview = QtCore.pyqtSignal(object)
    signal_Files_Remain = QtCore.pyqtSignal(int, int, int, int, int, str, str)

    #pgwindow idx, progress_percentage, ts, total, idx, strFilename

    def __init__(self, parent: QtWidgets.QApplication):
        super().__init__()

        style = r'''
                    QWidget {
                        font-size:16px;
                        color: #ddd;
                        border: 2px solid #8f8f91; 
                        border-width:1px; 
                        border-style: solid;
                        background-color: #333;
                        min-height:24px; 
                    }
                    QTreeView::branch:has-siblings:!adjoins-item {
                        border-image: url(vline.png) 0;
                    }
                    
                    QTreeView::branch:has-siblings:adjoins-item {
                        border-image: url(branch-more.png) 0;
                    }
                    
                    QTreeView::branch:!has-children:!has-siblings:adjoins-item {
                        border-image: url(branch-end.png) 0;
                    }
                    
                    QTreeView::branch:has-children:!has-siblings:closed,
                    QTreeView::branch:closed:has-children:has-siblings {
                            border-image: none;
                            image: url(branch-closed.png);
                    }
                    
                    QTreeView::branch:open:has-children:!has-siblings,
                    QTreeView::branch:open:has-children:has-siblings  {
                            border-image: none;
                            image: url(branch-open.png);
                    }
                    QHeaderView::section {
                        background-color: #333;
                    }
                '''
        self.css = style

        self.setWindowTitle('Transcoder')
        self.setAcceptDrops(True)

        self.btn_start = QtWidgets.QPushButton(r'轉檔')
        self.btn_clear = QtWidgets.QPushButton(r'清除')

        self.pg_dialog = [ProgWindow(0), ProgWindow(1)]


        self.output_location = QtWidgets.QLineEdit(r'C:\Users\brt\Desktop\VBOX')

        self.model = QtGui.QStandardItemModel()

        self.treeview = QtWidgets.QTreeView()
        self.treeview.setHeaderHidden(True)
        self.treeview.setModel(self.model)
        self.treeview.media_files = []

        self.treeview.setStyleSheet(style)
        self.treeview.setAcceptDrops(True)
        self.treeview.setMinimumSize(780, 400)
        self.treeview.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.gridLayoutWidget = QtWidgets.QGridLayout()
        self.gridLayoutWidget.addWidget(self.output_location,   0, 0, 1, 6)
        self.gridLayoutWidget.addWidget(self.btn_clear,         0, 6, 1, 2)
        self.gridLayoutWidget.addWidget(self.btn_start,         0, 8, 1, 2)
        self.gridLayoutWidget.addWidget(self.treeview,          1, 0, 1, 10)

        self.setLayout(self.gridLayoutWidget)
        self.setStyleSheet(style)

        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'convert-icon.png')))
        #self.resize(800, 600) 會破壞sizepolicy

        #順序對調會失效
        self.show()
        self.setMinimumSize(800, 600)
        self.btn_start.clicked.connect(self.transcode)
        self.btn_clear.clicked.connect(self.clear)

        self.signal_Update_Treeview.connect(self.update_treeview, QtCore.Qt.QueuedConnection)
        self.signal_Files_Remain.connect(lambda pgwinidx, pgval, ts, total, idx, strFilename, filesize: self.update_pg_dialog(
            pgwinidx, pgval, ts, total, idx, strFilename, filesize), QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot(int, int, int, int, int, str, str)
    def update_pg_dialog(self, pgwinidx, pgval, ts, total, idx, strFileName, filesize=''):
        self.pg_dialog[pgwinidx].setValue(pgval)
        self.pg_dialog[pgwinidx].setLabelText(
            strFileName[:30] + ' @' + str(ts) + ' sec - Files: ' + str(idx) + '/' + str(total))
        self.pg_dialog[pgwinidx].setWindowTitle('{0}%-{1}/{2} [{3}]'.format(pgval, idx, total, filesize))

    @QtCore.pyqtSlot(object)
    def trans_job_handler(self, job_queue: queue.Queue):

        m = re.compile(r'time=[0-9]+[:][0-9]+[:][0-9]+')
        winPosition = [[100, 100], [200, 200]]

        file_num = job_queue.qsize()
        workers = []    # Pascal 最多可同時啟用兩個 nvenc 單元

        for pgwin in self.pg_dialog:
            pgwin.signal_Hide.emit()

        while True:
            try:
                workers.append(job_queue.get())
            except queue.Empty:
                if len(workers) == 0:
                    # 工作完成 離開重複迴圈
                    self.signal_Files_Remain.emit(0, 100, 0, file_num, file_num, " ")
                    self.signal_Files_Remain.emit(1, 100, 0, file_num, file_num, " ")
                    break

            workers[-1].transcode(self.output_location.text())
            workers[-1].jobID = file_num - job_queue.qsize()

            for pgwin in self.pg_dialog:
                if not pgwin.flag_Using:
                    workers[-1].pgwinID = pgwin.idx
                    print(workers[-1].pgwinID)
                    pgwin.signal_Flag_Using_Set.emit(True)
                    pgwin.signal_ShowNormal.emit()
                    break

            # 剩下兩個 進度視窗 同時顯示 需要處理的部份
            interval = 0
            while job_queue.qsize() <= 0 or len(workers) >= 2:
                interval = (interval+1) % 10
                for worker in workers:
                    if worker.proc.poll() is not None:
                        print(worker.source_file)
                        self.signal_Files_Remain.emit(worker.pgwinID, 100, 0, file_num, worker.jobID, " ", " ")
                        self.pg_dialog[worker.pgwinID].signal_Flag_Using_Set.emit(False)
                        workers.remove(worker)
                        break
                        # print('{}'.format((int(pg/self.duration*100), )))
                        #print("{0} - {1} -> {2:.1f}%".format(media_obj.duration, pg, (float(pg) / float(media_obj.duration)) * 100))

                    pg, filesize = worker.progress    # 避免 main thread 卡在物件那邊等待多次讀取 所以先 deep-copy 一份出來
                    if pg is not None:
                        self.signal_Files_Remain.emit(worker.pgwinID, int(float(pg) / float(worker.duration) * 100), pg,
                            file_num, worker.jobID, worker.source.fileName(), filesize)

                    if interval == 0:
                        self.pg_dialog[worker.pgwinID].signal_MoveDialog.emit()
                        for pgwin in self.pg_dialog:
                            if not pgwin.flag_Using:
                                pgwin.signal_Hide.emit()

                time.sleep(0.005)



    @QtCore.pyqtSlot()
    def transcode(self):
        self.showMinimized()
        self.pg_dialog[0].setValue(0)
        #self.pg_dialog[0].showNormal()
        self.pg_dialog[1].setValue(0)
        #self.pg_dialog[1].showNormal()

        job_queue = queue.Queue()
        for item in self.treeview.media_files:
            job_queue.put_nowait(item)

        Thread(name='transcode', target=self.trans_job_handler, kwargs={"job_queue": job_queue}).start()

    @QtCore.pyqtSlot()
    def clear(self):
        self.treeview.media_files[:] = []
        self.treeview.model().clear()


    def probe_file(self, qfinfo: QtCore.QFileInfo):
        # 利用 ffprobe 分析檔案後 將資料建立成 Media Object 傳送給自訂的資料模型
        media_file = media(qfinfo.absoluteFilePath())
        self.signal_Update_Treeview.emit(media_file)    # 觸發 GUI thread - self.update_treeview()

    @QtCore.pyqtSlot(object)
    def update_treeview(self, media_file: media):
        self.model.appendRow(media_file.model_item)
        self.treeview.media_files.append(media_file)
        #self.model.setHorizontalHeaderItem(0, QtGui.QStandardItem(str(self.model.rowCount())))
        #self.treeview.expandAll()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        #print(event.mimeData().urls())
        for url in event.mimeData().urls():
            qfinfo = QtCore.QFileInfo(url.toLocalFile())
            Thread(name='ffprobe', target=self.probe_file, kwargs={"qfinfo": qfinfo}).start()


def main():
    #sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='xmlcharrefreplace')
    app = QtWidgets.QApplication(sys.argv)
    # 搜尋 py檔案所在的目錄內的 icon 檔案
    # app.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'search-website-512.png')))

    ui_widget = UIWidget(app)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()