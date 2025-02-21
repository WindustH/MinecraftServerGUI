from PyQt5.QtWidgets import QApplication
import sys
import json
import os
from ui import UI
CONFIG_FILE="config.json"

if __name__ == "__main__":
    with open(CONFIG_FILE, "r", encoding="utf-8") as configfile:
        config = json.load(configfile)
    settings = config["settings"]
    settings["git_dir"]=os.path.abspath(settings["git_dir"])
    settings["src_dir"]=os.path.abspath(settings["src_dir"])
    settings["tray_icon"]=os.path.abspath(settings["tray_icon"])
    settings["window_icon"]=os.path.abspath(settings["window_icon"])
    settings["stylesheet"]=os.path.abspath(settings["stylesheet"])

    work_dir=os.path.abspath(settings["work_dir"])
    os.chdir(work_dir)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    ui_instance = UI(settings)
    app.aboutToQuit.connect(ui_instance.when_about_to_quit)
    ui_instance.show()
    sys.exit(app.exec_())