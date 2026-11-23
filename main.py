"""ClassVision: AI attendance and exam monitoring.   Run:  python main.py"""
import logging
import os
import sys

# Set before OpenCV opens any stream: TCP is far more reliable than UDP for RTSP cameras.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run:  pip install -r requirements.txt")
        return 1
    from app.config import APP_NAME
    from app.context import AppContext
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme
    from app.vision import models

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app)
    ctx = AppContext()
    app.aboutToQuit.connect(ctx.close)
    window = MainWindow(ctx)
    window.show()
    if models.missing_models():
        QTimer.singleShot(400, window.prompt_models)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
