"""Generate a multi-size Windows ICO from the vector application icon."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parent
SVG_PATH = ROOT / "assets" / "MiniRadioPlayer.svg"
PNG_PATH = ROOT / "assets" / ".MiniRadioPlayer-build.png"
ICO_PATH = ROOT / "assets" / "MiniRadioPlayer.ico"


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])

    renderer = QSvgRenderer(str(SVG_PATH))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG icon: {SVG_PATH}")

    image = QImage(512, 512, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()

    if not image.save(str(PNG_PATH), "PNG"):
        raise RuntimeError(f"Failed to render icon: {PNG_PATH}")

    try:
        with Image.open(PNG_PATH) as source:
            source.convert("RGBA").save(
                ICO_PATH,
                format="ICO",
                sizes=[
                    (16, 16),
                    (24, 24),
                    (32, 32),
                    (48, 48),
                    (64, 64),
                    (128, 128),
                    (256, 256),
                ],
            )
    finally:
        PNG_PATH.unlink(missing_ok=True)

    print(f"Generated: {ICO_PATH}")


if __name__ == "__main__":
    main()
