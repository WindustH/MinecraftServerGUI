import datetime
import json
import re
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from server_manager import Server_Manager
from backup_manager import Backup_Manager
from utils import Listener_for_Specific_Output, Wait_for_a_Signal

ROLE = "Core"


class Core(QObject):
    sig_out = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()

        self.is_backing_up = False

        self.backup_interval = settings.get("backup_interval", 1800)
        self.info_update_interval = settings.get("info_update_interval", 1)
        self.timestamp_format = settings.get("timestamp_format", "%H:%M:%S")
        self.auto_backup = settings.get("auto_backup", True)
        self.backup_when_players_online = settings.get("backup_when_players_online", True)
        self.start_server_at_startup = settings.get("start_server_at_startup", True)

        self.server = Server_Manager(settings)
        self.backup_manager = Backup_Manager(settings)
        self.update_info_timer = QTimer()
        self.backup_timer = QTimer()
        self.player_cmd_listener = Listener_for_Specific_Output(
            self.server.sig_server_out, lambda x: "$" in x and "<" in x and ">" in x
        )

        self.update_info_timer.timeout.connect(self.server.update_server_info)
        self.backup_timer.timeout.connect(self.when_time_to_backup)
        self.backup_manager.sig_task_done.connect(self.when_backup_done)
        self.player_cmd_listener.sig.connect(self.when_detected_player_cmd)
        if self.start_server_at_startup:

            self.start_server()

    def start_server(self):
        self.server.start_server()
        self.update_info_timer.start(self.info_update_interval * 1000)
        if self.auto_backup:
            self.backup_timer.start(self.backup_interval * 1000)
        self.player_cmd_listener.start()

    def stop_server(self):
        self.server.stop_server()
        self.update_info_timer.stop()
        if self.auto_backup:
            self.backup_timer.stop()
        self.player_cmd_listener.stop()

    def stop_server_and_wait_to_stopped(self):
        self.server.stop_server_and_wait_to_stopped()
        self.update_info_timer.stop()
        if self.auto_backup:
            self.backup_timer.stop()
        self.player_cmd_listener.stop()

    def when_backup_done(self):
        self.is_backing_up = False
        self.server.server_exec_and_get_output(
            "save-on", lambda x: "Automatic saving is now enabled" in x
        )

    def when_time_to_backup(self):
        if self.is_backing_up:
            self.out(ROLE, "WARN", "A backup thread is running")
            return
        if self.server.is_running and self.auto_backup:
            if self.backup_when_players_online and self.server.player_count == 0:
                self.out(ROLE, "INFO", "No player online and skipped the backup")
                return
            self.server.server_exec("save-off")
            self.server.server_exec_and_get_output(
                "save-all", lambda x: "Saved the game" in x
            )
            self.is_backing_up = True
            self.backup_manager.run_task(self.backup_manager.new_auto_backup)

    def when_about_to_quit(self):
        if self.is_backing_up:
            block = Wait_for_a_Signal(self.backup_manager.sig_task_done)
            block.loop.exec()

        self.backup_manager.when_about_to_quit()
        self.server.when_about_to_quit()
        self.sig_out.disconnect()

    def when_detected_player_cmd(self, line):
        pattern = r"^.+? <(.*?)> \$([a-zA-Z0-9_]+) (.+)$"
        match = re.match(pattern, line.strip())

        if not match:
            return

        sender = match.group(1)
        command = match.group(2)
        option_json = match.group(3)

        try:
            option = json.loads(option_json)
            option["sender"] = sender
        except json.JSONDecodeError:
            self.out(
                ROLE, "WARN", f'"{line}" has option which is not in valid JSON format'
            )
            return
        self.core_exec(command, option)

    def out(self, role, flag, line):
        current_time = datetime.datetime.now().strftime(self.timestamp_format)
        self.sig_out.emit(f"[{current_time}] [{role}/{flag}]: {line}")

    def core_exec(self, command, option):
        if command == "backup":
            if self.is_backing_up:
                self.out(ROLE, "WARN", "A backup thread is running")
                return
            action = option.get("action")
            if action == None:
                self.out(
                    ROLE, "WARN", f'"action" option for "backup" command is missing'
                )
                return
            elif action == "new":
                self.is_backing_up = True
                self.server.server_exec("save-off")
                self.server.server_exec_and_get_output(
                    "save-all", lambda x: "Saved the game" in x
                )
                tag = option.get("tag")
                if tag == None:
                    self.backup_manager.run_task(self.backup_manager.new_auto_backup)
                else:
                    self.backup_manager.run_task(
                        self.backup_manager.new_tagged_backup, (tag,)
                    )
            elif action == "cl":
                self.is_backing_up = True
                self.backup_manager.run_task(self.backup_manager.clean)
            elif action == "ls":
                auto_commits = self.backup_manager.get_commit_msg_by_msg_prefix(
                    self.backup_manager.backup_prefix
                )
                tagged_commits = self.backup_manager.get_commit_msg_by_msg_prefix(
                    self.backup_manager.tagged_backup_prefix
                )
                commits = auto_commits + tagged_commits
                out_str = "list all backups:\n"
                for branch in commits:
                    out_str += f"\t{branch}\n"
                self.out(ROLE, "INFO", out_str)
            elif action == "restore":
                name = option.get("name")
                if name == None:
                    self.out(
                        ROLE,
                        "WARN",
                        f'"name" option for "backup restore" command is missing',
                    )
                    return
                else:
                    self.is_backing_up = True
                    restart_later = self.server.is_running
                    if self.server.is_running:
                        self.stop_server_and_wait_to_stopped()
                    self.backup_manager.run_task(
                        self.backup_manager.new_branch, (name,)
                    )
                    if restart_later:
                        self.start_server()

    def exec(self, command):
        if command.startswith("$"):
            pattern = r"\$([a-zA-Z0-9_]+) (.+)$"
            match = re.match(pattern, command.strip())

            if not match:
                self.out(ROLE, "WARN", f'"{command}" is not a valid command')
                return

            command = match.group(1)
            option_json = match.group(2)

            try:
                option = json.loads(option_json)
            except json.JSONDecodeError:
                self.out(
                    ROLE,
                    "WARN",
                    f'"{command}" has option which is not in valid JSON format',
                )
                return
            self.core_exec(command, option)
        else:
            self.server.server_exec(command)
