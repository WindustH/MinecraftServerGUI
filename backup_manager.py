import os
import subprocess
import datetime
from PyQt5.QtCore import pyqtSignal, QObject
import threading

ROLE = "Backup Manager"


class Backup_Manager(QObject):
    sig_out = pyqtSignal(str)
    sig_task_done = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        relative_src_dir=settings.get("src_dir")
        relative_git_dir=settings.get("git_dir")
        if relative_src_dir == None:
            raise KeyError(
                'Can\'t find option "src_dir". Please add it in config.json'
            )
        if relative_git_dir == None:
            raise KeyError(
                'Can\'t find option "git_dir". Please add it in config.json'
            )
        self.src_dir = os.path.abspath(relative_src_dir)
        self.git_dir = os.path.abspath(relative_git_dir)
        self.timestamp_format = settings.get("timestamp_format", "%Y%m%d%H%M%S")
        self.backup_prefix = settings.get("backup_prefix", "backup_")
        self.tagged_backup_prefix = settings.get("tagged_backup_prefix", "tag_")
        self.backup_timestamp_format = settings.get("backup_timestamp_format", "%Y%m%d%H%M%S")

    def get_commits_hash_by_msg_prefix(self, commit_prefix):
        try:
            output = subprocess.check_output(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "log",
                    "--all",
                    r"--grep=^" + commit_prefix,
                    "--pretty=format:%H",
                ],
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            commits_hash = output.split("\n")
            return commits_hash
        except subprocess.CalledProcessError as e:
            self.out(ROLE, "ERROR", f"Get commits by message prefix failed: {str(e)}")

    def get_commit_msg_by_msg_prefix(self, commit_prefix):
        try:
            output = subprocess.check_output(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "log",
                    "--all",
                    r"--grep=^" + commit_prefix,
                    "--pretty=format:%s",
                ],
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            commits_message = output.split("\n")
            return commits_message
        except subprocess.CalledProcessError as e:
            self.out(ROLE, "ERROR", f"Get commits by message prefix failed: {str(e)}")

    def get_commit_hash_by_msg(self, commit_message):
        try:
            output = subprocess.check_output(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "log",
                    "--all",
                    "--grep",
                    commit_message,
                    "--fixed-strings",
                    "--pretty=format:%H",
                ],
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            commits_hash = output.split("\n")
            if len(commits_hash) == 0:
                self.out(ROLE, "WARN", f"Can't find commit: {commit_message}")
                return None
            else:
                return commits_hash[0]
        except subprocess.CalledProcessError as e:
            self.out(ROLE, "ERROR", f"Get the commit by message failed: {str(e)}")

    def backup_timestamp(self):
        return datetime.datetime.now().strftime(self.backup_timestamp_format)

    def out(self, role, flag, line):
        current_time = datetime.datetime.now().strftime(self.timestamp_format)
        self.sig_out.emit(f"[{current_time}] [{role}/{flag}]: {line}")

    def new_commit(self, commit_msg):
        self.out(ROLE, "INFO", f"Starting backup: {commit_msg}")
        if not os.path.exists(self.git_dir):
            os.makedirs(self.git_dir)
        try:
            ignore_file = os.path.join(self.src_dir, ".gitignore")
            attribute_file = os.path.join(self.src_dir, ".gitattributes")
            with open(ignore_file, "w") as f:
                f.write("*.lock\n")
            with open(attribute_file, "w") as f:
                f.write("* binary\n")
            if not os.path.exists(os.path.join(self.git_dir, "HEAD")):
                subprocess.run(
                    ["git", "init", "--bare"],
                    cwd=self.git_dir,
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "--work-tree",
                    self.src_dir,
                    "reset"
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "--work-tree",
                    self.src_dir,
                    "add",
                    "--all",
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "--work-tree",
                    self.src_dir,
                    "commit",
                    "-m",
                    commit_msg,
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.out(ROLE, "INFO", f"Backup completed: {commit_msg}")

        except subprocess.CalledProcessError as e:
            self.out(ROLE, "ERROR", f"Backup failed: {str(e)}")
        finally:
            if os.path.exists(ignore_file):
                os.remove(ignore_file)
            if os.path.exists(attribute_file):
                os.remove(attribute_file)

    def clean(self):
        self.out(ROLE, "INFO", f"Cleaning git repo...")
        try:
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    self.git_dir,
                    "reflog",
                    "expire",
                    "--expire=now",
                    "--all",
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            subprocess.run(
                ["git", "--git-dir", self.git_dir, "gc", "--prune=now", "--aggressive"],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.out(ROLE, "INFO", f"Cleaned git repo")
        except subprocess.CalledProcessError as e:
            self.out(ROLE, "ERROR", f"Clean git repo failed: {str(e)}")

    def run_task(self, f, args=()):
        def thread_task():
            try:
                f(*args)
            except Exception as e:
                print(f"Error in thread_task: {e}")
            finally:
                self.sig_task_done.emit()

        thread = threading.Thread(target=thread_task)
        thread.start()

    def new_auto_backup(self):
        new_backup_name = self.backup_prefix + self.backup_timestamp()
        self.new_commit(new_backup_name)

    def new_tagged_backup(self, tag):
        new_backup_name = self.tagged_backup_prefix + tag
        self.new_commit(new_backup_name)

    def when_about_to_quit(self):
        self.sig_out.disconnect()
        self.sig_task_done.disconnect()

    def new_branch(self, commit_msg):
        self.out(ROLE, "INFO", f"Rolling back to: {commit_msg}...")
        try:
            os.makedirs(self.src_dir, exist_ok=True)
            commit_hash = self.get_commit_hash_by_msg(commit_msg)
            branch_name = self.backup_timestamp() + "_to_" + commit_msg
            command = [
                "git",
                "--git-dir",
                self.git_dir,
                "--work-tree",
                self.src_dir,
                "checkout",
                "-b",
                branch_name,
                commit_hash,
                "--force",
            ]

            subprocess.run(
                command, check=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.out(
                ROLE,
                "INFO",
                f"Created branch {branch_name} from {commit_msg} and switched to new branch",
            )
        except subprocess.CalledProcessError as e:
            self.out(ROLE, "ERROR", f"Rollback failed: {str(e)}")
