from PyQt5.QtCore import pyqtSignal,QEventLoop,QObject

class Wait_for_a_Specific_Output(QObject):
    def __init__(self,sig_out,filter):
        super().__init__()
        self.loop=QEventLoop()
        self.result=None
        self.filter=filter
        self.sig_out=sig_out
        self.sig_out.connect(self.judge)
    def judge(self,line):
        if self.filter(line):
            try:
                self.sig_out.disconnect(self.judge)
            except TypeError:
                pass
            self.result=line
            self.loop.quit()

class Listener_for_Specific_Output(QObject):
    sig=pyqtSignal(str)
    def __init__(self,sig_out,filter):
        super().__init__()
        self.filter=filter
        self.sig_out=sig_out
    def judge(self,line):
        if self.filter(line):
            self.sig.emit(line)
    def start(self):
        self.sig_out.connect(self.judge)
    def stop(self):
        try:
            self.sig_out.disconnect(self.judge)
        except TypeError:
            pass

class Wait_for_a_Signal(QObject):
    def __init__(self,sig_trigger):
        super().__init__()
        self.loop=QEventLoop()
        self.sig_trigger=sig_trigger
        self.sig_trigger.connect(self.slot)
    def slot(self):
        try:
            self.sig_trigger.disconnect(self.slot)
        except TypeError:
            pass
        self.loop.quit()