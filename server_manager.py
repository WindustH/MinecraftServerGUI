import datetime
import psutil
from PyQt5.QtCore import QProcess, pyqtSignal

from utils import (
    Wait_for_a_Specific_Output,
    Listener_for_Specific_Output,
    Wait_for_a_Signal
    )

ROLE="Server Manager"

class Server_Manager(QProcess):
    sig_out = pyqtSignal(str)
    sig_server_out = pyqtSignal(str)
    sig_info_updated=pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.player_joined_listener = Listener_for_Specific_Output(
            self.sig_server_out, lambda x: "joined the game" in x
        )
        self.player_left_listener = Listener_for_Specific_Output(
            self.sig_server_out, lambda x: "left the game" in x
        )

        self.timestamp_format = settings.get("timestamp_format", "%H:%M:%S")
        self.start_command = settings.get("start_command")
        if self.start_command == None:
            raise KeyError(
                'Can\'t find option "start_command". Please add it in config.json'
            )
        self.is_running = False
        self.player_count = 0
        self.start_time = None
        self.cpu_usage = None
        self.memory_usage = None

        self.setProcessChannelMode(QProcess.MergedChannels)

        self.readyReadStandardOutput.connect(self.server_out)
        self.started.connect(self.when_server_started)
        self.finished.connect(self.when_server_finished)
        self.player_joined_listener.sig.connect(self.when_player_joined)
        self.player_left_listener.sig.connect(self.when_player_left)

    def start_server(self):
        if self.state() == QProcess.Running:
            self.shell_out(ROLE, "WARN", "Server is already running!")
            return

        self.shell_out(ROLE, "INFO", "Starting server...")

        self.start(self.start_command)

    def stop_server(self):
        if self.state() == QProcess.Running:
            self.shell_out(ROLE, "INFO", "Stopping server...")
            self.server_exec("stop")

        else:
            self.shell_out(ROLE, "WARN", "Server is not running.")

    def stop_server_and_wait_to_stopped(self):
        if self.is_running:
            block = Wait_for_a_Signal(self.finished)
            self.stop_server()
            block.loop.exec()

    def shell_out(self, role, flag, line):
        current_time = datetime.datetime.now().strftime(
            self.timestamp_format
        )
        self.sig_out.emit(f"[{current_time}] [{role}/{flag}]: {line}")

    def server_exec(self, command):
        if self.state() == QProcess.Running:
            self.write(f"{command}\n".encode())
        else:
            self.shell_out(ROLE, "WARN", "Server is not running.")

    def server_exec_silent(self, command):
        if self.state() == QProcess.Running:
            self.write(f"{command}\n".encode())

    def server_exec_and_get_output(self,command,filter):
        block=Wait_for_a_Specific_Output(self.sig_server_out,filter)
        self.server_exec(command)
        block.loop.exec()
        return block.result

    def server_out(self):
        output = self.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.sig_server_out.emit(output)

    def when_server_started(self):
        self.start_time = datetime.datetime.now()
        self.player_count = 0
        self.is_running = True
        self.player_joined_listener.start()
        self.player_left_listener.start()

    def when_server_finished(self):
        self.is_running = False
        self.start_time = None
        self.cpu_usage = None
        self.memory_usage = None
        self.player_joined_listener.stop()
        self.player_left_listener.stop()
        self.update_server_info()

    def when_player_joined(self):
        self.player_count+=1

    def when_player_left(self):
        self.player_count-=1

    def when_about_to_quit(self):
        self.player_joined_listener.stop()
        self.player_left_listener.stop()
        self.stop_server_and_wait_to_stopped()

        self.readyReadStandardOutput.disconnect()
        self.started.disconnect()
        self.finished.disconnect()
        self.sig_out.disconnect()
        self.sig_info_updated.disconnect()
        self.sig_server_out.disconnect()

    def update_server_info(self):
        if self.is_running:
            process = psutil.Process(self.processId())
            self.cpu_usage = process.cpu_percent(interval=None)
            self.memory_usage = process.memory_info().rss / (1024 * 1024)
        self.sig_info_updated.emit()
