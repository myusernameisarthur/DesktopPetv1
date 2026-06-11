"""Grab a screenshot of the right-click menu (with Idle submenu open) for the
Phase 2 report. Dev tool. Run: python tools/shot_menu.py"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="persi-shot-")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QPoint

app = QApplication(sys.argv)
import biscuit

dog = biscuit.Biscuit()
menu = dog._build_menu()
pos = QPoint(int(dog.dog_sx) - 120, dog.tb_top - 420)
menu.popup(pos)


def open_idle():
    idle_action = next(a for a in menu.actions()
                       if a.menu() is not None and a.menu().title() == "Idle")
    menu.setActiveAction(idle_action)
    idle_action.menu().popup(QPoint(pos.x() + menu.width(), pos.y() + 60))


def shoot():
    screen = QApplication.primaryScreen()
    pm = screen.grabWindow(0, pos.x() - 10, pos.y() - 10, 480, 460)
    out = os.path.join(ROOT, "verify", "phase2", "menu-grouped.png")
    pm.save(out)
    print("saved", out)
    app.exit(0)


QTimer.singleShot(400, open_idle)
QTimer.singleShot(900, shoot)
sys.exit(app.exec_())
