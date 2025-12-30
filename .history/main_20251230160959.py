"""
Mini Radio Player — Windows tray app (Python, PySide6)

Features
- Plays streaming URL (default: https://stream.ipdj.ru/listen/cafe/radio.mp3)
- Minimal window, can run in background, minimize to tray
- Autoplay schedule: 08:00–22:00 (configurable HH:MM)
- Play / Stop, Volume
- Persists settings in %APPDATA%/MiniRadioPlayer/settings.json

How to run
1) pip install -r requirements.txt  (PySide6)
2) python mini_radio.py

How to build .exe (optional)
- pip install pyinstaller
- pyinstaller --noconsole --name MiniRadioPlayer --onefile mini_radio.py
  (PyInstaller usually bundles QtMultimedia automatically; if not, add: --add-data "{pyside6_dir}/Qt/plugins;PySide6/Qt/plugins")
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, time as dtime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QSystemTrayIcon,
    QMenu,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QGroupBox,
    QGridLayout,
    QMessageBox,
    QStyle,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


APP_NAME = "MiniRadioPlayer"
DEFAULT_URL = "https://stream.ipdj.ru/listen/cafe/radio.mp3"


def app_data_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


SETTINGS_PATH = app_data_dir() / "settings.json"


@dataclass
class PlayerSettings:
    stream_url: str = DEFAULT_URL
    start_time: str = "08:00"  # HH:MM
    end_time: str = "22:00"    # HH:MM
    volume: float = 0.6         # 0..1
    start_minimized: bool = True

    @staticmethod
    def load() -> "PlayerSettings":
        try:
            if SETTINGS_PATH.exists():
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                return PlayerSettings(**data)
        except Exception:
            pass
        return PlayerSettings()

    def save(self) -> None:
        try:
            SETTINGS_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            pass


class MiniRadio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Radio")
        self.setFixedSize(380, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # State & settings
        self.settings = PlayerSettings.load()
        self.is_playing = False

        # Media
        self.audio = QAudioOutput()
        self.audio.setVolume(self.settings.volume)  # 0..1
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)
        self.player.errorOccurred.connect(self._on_error)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        # UI
        self._build_ui()

        # Tray
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.tray.setToolTip("Mini Radio Player")
        self._build_tray_menu()
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        # Scheduler
        self.timer = QTimer(self)
        self.timer.setInterval(20_000)  # 20s
        self.timer.timeout.connect(self._check_schedule_and_apply)
        self.timer.start()

        # Start minimized optionally
        if self.settings.start_minimized:
            QTimer.singleShot(0, self.hide)
        QTimer.singleShot(200, self._check_schedule_and_apply)

    # ---------------------- UI ----------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(4)

        # URL
        url_box = QVBoxLayout()
        url_label = QLabel("Stream URL")
        url_label.setStyleSheet("color: #bbb;")
        self.url_edit = QLineEdit(self.settings.stream_url)
        self.url_edit.setPlaceholderText("https://...")
        self.url_edit.setStyleSheet("padding:6px;")
        url_box.addWidget(url_label)
        url_box.addWidget(self.url_edit)
        root.addLayout(url_box)

        # Controls row
        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_stop = QPushButton("Stop")
        self.btn_play.clicked.connect(self.play)
        self.btn_stop.clicked.connect(self.stop)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_stop)

        vol_label = QLabel("Volume")
        vol_label.setStyleSheet("margin-left:8px; color:#bbb;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.settings.volume * 100))
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self.vol_percent = QLabel(f"{int(self.settings.volume * 100)}%")
        self.vol_percent.setStyleSheet("color:#bbb; margin-left:4px;")
        ctrl.addWidget(vol_label)
        ctrl.addWidget(self.vol_slider)
        ctrl.addWidget(self.vol_percent)
        root.addLayout(ctrl)

        # Schedule group
        grp = QGroupBox("               Auto play schedule")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("Start"), 0, 0)
        self.start_edit = QLineEdit(self.settings.start_time)
        self.start_edit.setMaximumWidth(80)
        self.start_edit.setPlaceholderText("HH:MM")
        self.start_edit.editingFinished.connect(self._format_time)
        grid.addWidget(self.start_edit, 0, 1)
        grid.addWidget(QLabel("End"), 0, 2)
        self.end_edit = QLineEdit(self.settings.end_time)
        self.end_edit.setMaximumWidth(80)
        self.end_edit.setPlaceholderText("HH:MM")
        self.end_edit.editingFinished.connect(self._format_time)
        grid.addWidget(self.end_edit, 0, 3)
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save)
        grid.addWidget(self.btn_save, 0, 4)
        grp.setLayout(grid)
        root.addWidget(grp)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color:#999;")
        root.addWidget(self.status_lbl)

        # Aesthetic (minimal dark)
        self.setStyleSheet(
            """
            QWidget { background:#111217; color:#f4f6f8; }
            QLineEdit, QGroupBox { background:#161821; border:1px solid #2a2d36; border-radius:4px; }
            QPushButton { background:#232633; border:1px solid #3a3f4b; padding:4px 8px; border-radius:4px; }
            QPushButton:hover { background:#2b2f3e; }
            QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 2px; }
            QSlider::groove:horizontal { height:4px; background:#2a2d36; border-radius:2px; }
            QSlider::handle:horizontal { width:12px; background:#5b6bff; margin:-4px 0; border-radius:6px; }
            """
        )

    def _build_tray_menu(self):
        menu = QMenu()
        act_open = QAction("Open", self)
        act_open.triggered.connect(self._show_window)
        act_play = QAction("Play", self)
        act_play.triggered.connect(self.play)
        act_stop = QAction("Stop", self)
        act_stop.triggered.connect(self.stop)
        act_quit = QAction("Exit", self)
        act_quit.triggered.connect(self._quit_app)
        menu.addAction(act_open)
        menu.addSeparator()
        menu.addAction(act_play)
        menu.addAction(act_stop)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)

    # ---------------------- Tray ----------------------
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # single click
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------------------- Player ----------------------
    def play(self):
        url = self.url_edit.text().strip()
        if not url:
            self._set_status("No URL")
            return
        self.target_volume = self.settings.volume
        self.audio.setVolume(0)
        self.player.setSource(QUrl(url))
        self.player.play()
        self.is_playing = True
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self._set_status("Playing…")
        self._persist_runtime_settings()
        self._fade_in_volume()

    def stop(self):
        self._fade_out_volume()

    def _on_volume_changed(self, value: int):
        vol = max(0.0, min(1.0, value / 100.0))
        self.audio.setVolume(vol)
        self.settings.volume = vol
        self.settings.save()
        self.vol_percent.setText(f"{value}%")

    def _on_state_changed(self, _state):
        # Keep simple — QMediaPlayer states are Managed by play/stop
        pass

    def _on_error(self, err, msg):
        # Qt 6 passes (QMediaPlayer.Error, str)
        self._set_status(f"Failed: {msg}")
        self.is_playing = False

    def _fade_in_volume(self):
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._step_fade_in)
        self.fade_timer.start(50)

    def _step_fade_in(self):
        current = self.audio.volume()
        step = 0.02
        if current < self.target_volume:
            new_vol = min(self.target_volume, current + step)
            self.audio.setVolume(new_vol)
        else:
            self.fade_timer.stop()

    def _fade_out_volume(self):
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._step_fade_out)
        self.fade_timer.start(50)

    def _step_fade_out(self):
        current = self.audio.volume()
        step = 0.02
        if current > 0:
            new_vol = max(0, current - step)
            self.audio.setVolume(new_vol)
        else:
            self.fade_timer.stop()
            self.player.stop()
            self.is_playing = False
            self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self._set_status("Stopped")

    # ---------------------- Schedule ----------------------
    def _parse_hhmm(self, s: str) -> dtime | None:
        try:
            h, m = s.split(":")
            return dtime(int(h), int(m))
        except Exception:
            return None

    def _format_time(self):
        sender = self.sender()
        if isinstance(sender, QLineEdit) and sender in (self.start_edit, self.end_edit):
            text = sender.text().strip()
            if len(text) == 4 and text.isdigit():
                hours = int(text[:2])
                minutes = int(text[2:])
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    sender.setText(f"{hours:02d}:{minutes:02d}")

    def _within_window(self, now: dtime, start: dtime, end: dtime) -> bool:
        if start == end:
            return False  # disabled if equal
        if end > start:
            return start <= now < end
        else:
            # across midnight
            return now >= start or now < end

    def _check_schedule_and_apply(self):
        now = datetime.now().time()
        st = self._parse_hhmm(self.settings.start_time) or dtime(8, 0)
        et = self._parse_hhmm(self.settings.end_time) or dtime(22, 0)
        within = self._within_window(now, st, et)
        if within and not self.is_playing:
            self.play()
        elif not within and self.is_playing:
            self.stop()

    # ---------------------- Persistence ----------------------
    def _persist_runtime_settings(self):
        self.settings.stream_url = self.url_edit.text().strip() or self.settings.stream_url
        self.settings.save()

    def _on_save(self):
        st = self._parse_hhmm(self.start_edit.text().strip())
        et = self._parse_hhmm(self.end_edit.text().strip())
        if not st or not et:
            QMessageBox.warning(self, "Invalid time", "Use HH:MM, e.g., 08:00 and 22:00")
            return
        self.settings.start_time = self.start_edit.text().strip()
        self.settings.end_time = self.end_edit.text().strip()
        self.settings.stream_url = self.url_edit.text().strip() or self.settings.stream_url
        self.settings.save()
        self._set_status("Saved")
        self._check_schedule_and_apply()

    def _set_status(self, text: str):
        self.status_lbl.setText(text)

    def _quit_app(self):
        QApplication.quit()

    # ---------------------- Window overrides ----------------------
    def closeEvent(self, event):  # minimize to tray on close (X)
        event.ignore()
        self.hide()
        if self.tray.isVisible():
            self.tray.showMessage(
                "Mini Radio",
                "Still running in tray. Right‑click the icon for options.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = MiniRadio()
    w.show()  # will hide immediately if start_minimized
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
