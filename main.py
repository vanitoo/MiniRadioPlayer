"""
Mini Radio Player — Windows tray app (Python, PySide6).

Features
- Plays a streaming URL.
- Minimal window with system tray support.
- Configurable autoplay schedule, including windows across midnight.
- Play / Stop with smooth volume fade.
- Persists settings in %APPDATA%/MiniRadioPlayer/settings.json.
"""

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QAction
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "MiniRadioPlayer"

STATIONS = {
    "Cafe — Soulful House": "https://stream.ipdj.ru/listen/cafe/radio.mp3",
    "Restaurant — Lounge": "https://stream.ipdj.ru/listen/restouran/radio.mp3",
    "Beer Restaurant — Jazz & Blues": "https://stream.ipdj.ru/listen/pivrest/radio.mp3",
    "Bar — Rock & Grunge": "https://stream.ipdj.ru/listen/bar/radio.mp3",
    "Barbershop — Rap & Bass House": "https://stream.ipdj.ru/listen/barber/radio.mp3",
}
CUSTOM_STATION = "Custom URL"
DEFAULT_URL = STATIONS["Cafe — Soulful House"]

SCHEDULE_INTERVAL_MS = 20_000
RETRY_DELAY_SECONDS = 60
FADE_INTERVAL_MS = 50
FADE_STEP = 0.02


def app_data_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_PATH = app_data_dir() / "settings.json"


@dataclass
class PlayerSettings:
    stream_url: str = DEFAULT_URL
    start_time: str = "08:00"
    end_time: str = "22:00"
    volume: float = 0.6
    start_minimized: bool = True

    @staticmethod
    def load() -> "PlayerSettings":
        if not SETTINGS_PATH.exists():
            return PlayerSettings()

        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return PlayerSettings()

            volume = float(data.get("volume", 0.6))
            return PlayerSettings(
                stream_url=str(data.get("stream_url", DEFAULT_URL)) or DEFAULT_URL,
                start_time=str(data.get("start_time", "08:00")),
                end_time=str(data.get("end_time", "22:00")),
                volume=max(0.0, min(1.0, volume)),
                start_minimized=bool(data.get("start_minimized", True)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return PlayerSettings()

    def save(self) -> bool:
        try:
            SETTINGS_PATH.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False


class MiniRadio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Radio")
        self.setFixedSize(440, 265)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.settings = PlayerSettings.load()
        self.is_playing = False
        self._last_error_message: str | None = None
        self._next_retry_at: datetime | None = None

        self.audio = QAudioOutput()
        self.audio.setVolume(self.settings.volume)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)
        self.player.errorOccurred.connect(self._on_error)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        self.fade_timer = QTimer(self)
        self.fade_timer.setInterval(FADE_INTERVAL_MS)
        self.fade_timer.timeout.connect(self._step_fade)
        self._fade_target = self.settings.volume
        self._stop_after_fade = False

        self._build_ui()

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.tray.setToolTip("Mini Radio Player")
        self._build_tray_menu()
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.timer = QTimer(self)
        self.timer.setInterval(SCHEDULE_INTERVAL_MS)
        self.timer.timeout.connect(self._check_schedule_and_apply)
        self.timer.start()

        if self.settings.start_minimized:
            QTimer.singleShot(0, self.hide)
        QTimer.singleShot(200, self._check_schedule_and_apply)

    # ---------------------- UI ----------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(5)

        station_box = QVBoxLayout()
        station_label = QLabel("Station")
        station_label.setStyleSheet("color: #bbb;")

        self.station_combo = QComboBox()
        self.station_combo.addItems([*STATIONS.keys(), CUSTOM_STATION])

        current_station = self._station_name_for_url(self.settings.stream_url)
        self.station_combo.setCurrentText(current_station)

        self.url_edit = QLineEdit(self.settings.stream_url)
        self.url_edit.setPlaceholderText("https://...")
        self.url_edit.setStyleSheet("padding:6px;")
        self.url_edit.setReadOnly(current_station != CUSTOM_STATION)

        self.station_combo.currentTextChanged.connect(self._on_station_changed)

        station_box.addWidget(station_label)
        station_box.addWidget(self.station_combo)

        url_label = QLabel("Stream URL")
        url_label.setStyleSheet("color: #bbb;")
        station_box.addWidget(url_label)
        station_box.addWidget(self.url_edit)
        root.addLayout(station_box)

        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_stop = QPushButton("Stop")
        self.btn_play.clicked.connect(lambda: self.play())
        self.btn_stop.clicked.connect(self.stop)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_stop)

        vol_label = QLabel("Volume")
        vol_label.setStyleSheet("margin-left:8px; color:#bbb;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(round(self.settings.volume * 100))
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self.vol_percent = QLabel(f"{round(self.settings.volume * 100)}%")
        self.vol_percent.setStyleSheet("color:#bbb; margin-left:4px;")
        ctrl.addWidget(vol_label)
        ctrl.addWidget(self.vol_slider)
        ctrl.addWidget(self.vol_percent)
        root.addLayout(ctrl)

        grp = QGroupBox("Auto play schedule")
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

        self.start_minimized_check = QCheckBox("Start minimized")
        self.start_minimized_check.setChecked(self.settings.start_minimized)
        grid.addWidget(self.start_minimized_check, 1, 0, 1, 3)

        grp.setLayout(grid)
        root.addWidget(grp)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color:#999;")
        root.addWidget(self.status_lbl)

        self.setStyleSheet(
            """
            QWidget { background:#111217; color:#f4f6f8; }
            QLineEdit, QComboBox, QGroupBox {
                background:#161821;
                border:1px solid #2a2d36;
                border-radius:4px;
            }
            QPushButton {
                background:#232633;
                border:1px solid #3a3f4b;
                padding:4px 8px;
                border-radius:4px;
            }
            QPushButton:hover { background:#2b2f3e; }
            QGroupBox::title {
                subcontrol-origin: margin;
                left:8px;
                padding:0 2px;
            }
            QSlider::groove:horizontal {
                height:4px;
                background:#2a2d36;
                border-radius:2px;
            }
            QSlider::handle:horizontal {
                width:12px;
                background:#5b6bff;
                margin:-4px 0;
                border-radius:6px;
            }
            """
        )

    def _build_tray_menu(self):
        menu = QMenu()

        act_open = QAction("Open", self)
        act_open.triggered.connect(self._show_window)

        act_play = QAction("Play", self)
        act_play.triggered.connect(lambda: self.play())

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
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------------------- Stations ----------------------
    def _station_name_for_url(self, url: str) -> str:
        for name, station_url in STATIONS.items():
            if url == station_url:
                return name
        return CUSTOM_STATION

    def _on_station_changed(self, station_name: str):
        station_url = STATIONS.get(station_name)
        is_custom = station_url is None

        self.url_edit.setReadOnly(not is_custom)

        if is_custom:
            self.url_edit.setFocus()
            self.url_edit.selectAll()
            self._set_status("Enter custom stream URL")
            return

        self.url_edit.setText(station_url)
        self.settings.stream_url = station_url
        self.settings.save()

        if self.is_playing:
            self.play()
        else:
            self._set_status(f"Selected: {station_name}")

    # ---------------------- Player ----------------------
    def play(self, *, scheduled: bool = False):
        url = self.url_edit.text().strip()
        if not url:
            self._set_status("No URL")
            return

        if not scheduled:
            self._next_retry_at = None

        self._last_error_message = None
        self._stop_after_fade = False
        self.audio.setVolume(0.0)
        self.player.setSource(QUrl(url))
        self.player.play()
        self._persist_runtime_settings()
        self._start_fade(self.settings.volume, stop_after=False)
        station_name = self._station_name_for_url(url)
        if station_name == CUSTOM_STATION:
            self._set_status("Connecting to custom stream…")
        else:
            self._set_status(f"Connecting: {station_name}…")

    def stop(self):
        if (
            self.player.playbackState()
            == QMediaPlayer.PlaybackState.StoppedState
            and not self.fade_timer.isActive()
        ):
            self._set_stopped_ui()
            return

        self._last_error_message = None
        self._set_status("Stopping…")
        self._start_fade(0.0, stop_after=True)

    def _start_fade(self, target: float, *, stop_after: bool):
        self._fade_target = max(0.0, min(1.0, target))
        self._stop_after_fade = stop_after

        if abs(self.audio.volume() - self._fade_target) < 0.001:
            self._finish_fade()
            return

        if not self.fade_timer.isActive():
            self.fade_timer.start()

    def _step_fade(self):
        current = self.audio.volume()
        target = self._fade_target
        delta = target - current

        if abs(delta) <= FADE_STEP:
            self.audio.setVolume(target)
            self._finish_fade()
            return

        self.audio.setVolume(current + (FADE_STEP if delta > 0 else -FADE_STEP))

    def _finish_fade(self):
        self.fade_timer.stop()
        if self._stop_after_fade and self._fade_target <= 0.0:
            self._stop_after_fade = False
            self.player.stop()

    def _on_volume_changed(self, value: int):
        volume = max(0.0, min(1.0, value / 100.0))
        self.settings.volume = volume
        self.vol_percent.setText(f"{value}%")

        if self.is_playing and not self._stop_after_fade:
            if self.fade_timer.isActive():
                self._fade_target = volume
            else:
                self.audio.setVolume(volume)
        elif not self.is_playing:
            self.audio.setVolume(volume)

        self.settings.save()

    def _on_state_changed(self, state):
        self.is_playing = state == QMediaPlayer.PlaybackState.PlayingState

        if self.is_playing:
            self._next_retry_at = None
            self.tray.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )
            self._set_status("Playing")
            return

        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.tray.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
            if self._last_error_message:
                self._set_status(f"Failed: {self._last_error_message}")
            else:
                self._set_status("Stopped")

    def _on_error(self, _error, message):
        self.fade_timer.stop()
        self._stop_after_fade = False
        self._last_error_message = message or "Unknown media error"
        self._next_retry_at = datetime.now() + timedelta(
            seconds=RETRY_DELAY_SECONDS
        )
        self.player.stop()
        self.is_playing = False
        self.tray.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self._set_status(f"Failed: {self._last_error_message}")

    def _set_stopped_ui(self):
        self.is_playing = False
        self.tray.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self._set_status("Stopped")

    # ---------------------- Schedule ----------------------
    def _parse_hhmm(self, value: str) -> dtime | None:
        try:
            hours, minutes = value.split(":")
            return dtime(int(hours), int(minutes))
        except (ValueError, TypeError):
            return None

    def _format_time(self):
        sender = self.sender()
        if not isinstance(sender, QLineEdit):
            return
        if sender not in (self.start_edit, self.end_edit):
            return

        text = sender.text().strip()
        if len(text) == 4 and text.isdigit():
            hours = int(text[:2])
            minutes = int(text[2:])
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                sender.setText(f"{hours:02d}:{minutes:02d}")

    def _within_window(self, now: dtime, start: dtime, end: dtime) -> bool:
        if start == end:
            return False
        if end > start:
            return start <= now < end
        return now >= start or now < end

    def _check_schedule_and_apply(self):
        now_dt = datetime.now()
        now = now_dt.time()

        start = self._parse_hhmm(self.settings.start_time) or dtime(8, 0)
        end = self._parse_hhmm(self.settings.end_time) or dtime(22, 0)
        within = self._within_window(now, start, end)

        if within and not self.is_playing:
            if self._next_retry_at and now_dt < self._next_retry_at:
                return
            self.play(scheduled=True)
        elif not within and (
            self.is_playing
            or self.player.playbackState()
            != QMediaPlayer.PlaybackState.StoppedState
        ):
            self.stop()

    # ---------------------- Persistence ----------------------
    def _persist_runtime_settings(self):
        self.settings.stream_url = (
            self.url_edit.text().strip() or self.settings.stream_url
        )
        self.settings.save()

    def _on_save(self):
        start = self._parse_hhmm(self.start_edit.text().strip())
        end = self._parse_hhmm(self.end_edit.text().strip())

        if not start or not end:
            QMessageBox.warning(
                self,
                "Invalid time",
                "Use HH:MM, e.g. 08:00 and 22:00.",
            )
            return

        self.settings.start_time = f"{start.hour:02d}:{start.minute:02d}"
        self.settings.end_time = f"{end.hour:02d}:{end.minute:02d}"
        self.start_edit.setText(self.settings.start_time)
        self.end_edit.setText(self.settings.end_time)
        self.settings.stream_url = (
            self.url_edit.text().strip() or self.settings.stream_url
        )
        self.settings.start_minimized = self.start_minimized_check.isChecked()

        if not self.settings.save():
            QMessageBox.warning(
                self,
                "Save failed",
                f"Could not write settings to:\n{SETTINGS_PATH}",
            )
            return

        self._set_status("Saved")
        self._check_schedule_and_apply()

    def _set_status(self, text: str):
        self.status_lbl.setText(text)

    def _quit_app(self):
        self.fade_timer.stop()
        self.player.stop()
        QApplication.quit()

    # ---------------------- Window overrides ----------------------
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if self.tray.isVisible():
            self.tray.showMessage(
                "Mini Radio",
                "Still running in tray. Right-click the icon for options.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MiniRadio()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
