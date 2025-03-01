import sys
import datetime
import time

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QLabel,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5 import QtGui
from core import Core

ROLE="UI"
USER_ROLE="User"

class UI(QWidget):
    sig_out=pyqtSignal(str)
    def __init__(self,settings):
        super().__init__()

        self.timestamp_format=settings.get('timestamp_format', '%H:%M:%S')
        self.stylesheet_path=settings.get('stylesheet', 'styles/MacOS.qss')
        self.ui_font=settings.get('font', 'Arial')
        self.ui_font_size=settings.get('font_size', 12)
        self.tray_icon_path=settings.get('tray_icon', 'res/minecraft_icon.ico')
        self.window_icon_path=settings.get('window_icon', 'res/minecraft_icon.ico')
        self.colormap=settings.get('cmdl_colormap', {})
        self.output_exclude=settings.get('cmdl_output_exclude', [])

        self.core=Core(settings)

        self.init_ui()
        self.init_tray_icon()

        self.sig_out.connect(self.cmdl_output_catcher)
        self.core.sig_out.connect(self.cmdl_output_catcher)
        self.core.server.sig_server_out.connect(self.cmdl_output_catcher)
        self.core.server.sig_out.connect(self.cmdl_output_catcher)
        self.core.backup_manager.sig_out.connect(self.cmdl_output_catcher)
        self.core.server.sig_info_updated.connect(self.when_server_info_updated)

        self.core.sig_out.connect(self.ingame_output_catcher)
        self.core.server.sig_out.connect(self.ingame_output_catcher)
        self.core.backup_manager.sig_out.connect(self.ingame_output_catcher)

    def init_ui(self):
        with open(self.stylesheet_path, encoding="utf-8") as f:
            qss_str = f.read()
        self.setStyleSheet(qss_str)
        font = QtGui.QFont(
            self.ui_font, self.ui_font_size, italic=True
        )
        QApplication.instance().setFont(font)

        layout = QVBoxLayout()
        button_layout = QHBoxLayout()
        self.cmdl = QTextEdit(self)
        self.server_info_label = QLabel(self)
        self.cmdl_input = QLineEdit(self)
        self.start_button = QPushButton("Start Server", self)
        self.stop_button = QPushButton("Stop Server", self)
        self.clear_button = QPushButton("Clear Output", self)

        self.cmdl_input.setPlaceholderText("Enter command")
        self.cmdl.setReadOnly(True)
        self.server_info_label.setWordWrap(True)
        self.server_info_label.setText("Server is not running")

        self.cmdl_input.returnPressed.connect(self.when_cmdl_input_returnPressed)
        self.start_button.clicked.connect(self.core.start_server)
        self.stop_button.clicked.connect(self.core.stop_server)
        self.clear_button.clicked.connect(self.cmdl.clear)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.clear_button)
        layout.addWidget(self.cmdl)
        layout.addWidget(self.server_info_label)
        layout.addWidget(self.cmdl_input)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setWindowIcon(QtGui.QIcon(self.window_icon_path))
        self.setWindowTitle("Minecraft Server GUI")  # 设置标题
        self.setWindowFlags(
            Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self.setGeometry(100, 100, 1000, 800)

        self.closeEvent = self.when_close_button_clicked

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        tray_menu = QMenu(self)
        show_action = QAction("Show", self)
        quit_action = QAction("Quit", self)

        show_action.triggered.connect(self.when_show_action_triggered)
        quit_action.triggered.connect(self.when_quit_action_triggered)
        self.tray_icon.activated.connect(self.when_tray_icon_activated)

        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setIcon(QtGui.QIcon(self.tray_icon_path))
        self.tray_icon.setVisible(True)

    def when_server_info_updated(self):
        if self.core.server.is_running:
            run_time = datetime.datetime.now() - self.core.server.start_time
            run_time_str = str(run_time).split(".")[0]
            self.server_info_label.setText(
                f"Server Uptime: {run_time_str}\n"
                f"CPU Usage: {self.core.server.cpu_usage:.2f}%\n"
                f"Memory Usage: {self.core.server.memory_usage:.2f} MB\n"
                f"Players Online: {self.core.server.player_count}"
            )
        else:
            self.server_info_label.setText("Server is not running")

    def when_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.when_show_action_triggered()

    def when_cmdl_input_returnPressed(self):
        command = self.cmdl_input.text()
        self.cmdl_input.clear()
        self.out(USER_ROLE, "INFO", command)
        self.core.exec(command)

    def when_close_button_clicked(self, event):
        event.ignore()
        self.hide()

    def when_quit_action_triggered(self):
        QApplication.instance().quit()

    def when_about_to_quit(self):
        self.core.when_about_to_quit()
        self.sig_out.disconnect()
        self.tray_icon.hide()
        self.close()

    def when_show_action_triggered(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def write_cmdl(self, output):
        color_map={}
        for key, value in self.colormap.items():
            color_map[key]=QtGui.QColor(value)
        lines = output.splitlines()
        cursor = self.cmdl.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        for line in lines:
            color = color_map.get(next((k for k in color_map if k in line), "__fallback__"), QtGui.QColor("black"))
            format = QtGui.QTextCharFormat()
            format.setForeground(color)
            cursor.insertText(line + "\n", format)
        self.cmdl.setTextCursor(cursor)

    def write_ingame(self,output):
        for line in output.splitlines():
            self.core.server.server_exec_silent(f"say {line}")

    def out(self, role, flag, line):
        current_time = datetime.datetime.now().strftime(self.timestamp_format)
        self.sig_out.emit(f"[{current_time}] [{role}/{flag}]: {line}")

    def cmdl_output_filter(self, line):
        for frag in self.output_exclude:
            if frag in line:
                return False
        return True

    def cmdl_output_catcher(self,line):
        if self.cmdl_output_filter(line):
            self.write_cmdl(line)

    def ingame_output_catcher(self,line):
        self.write_ingame(line)
