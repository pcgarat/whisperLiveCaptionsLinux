from __future__ import annotations

import queue
import sys
import traceback
from pathlib import Path

from PyQt6 import QtWidgets

from src.asr.pipeline import AsrPipeline
from src.asr.types import CaptionUpdate
from src.audio.devices import list_audio_monitors
from src.config import load_config, save_config
from src.ui.overlay import SubtitleOverlay
from src.ui.settings import SettingsDialog


class AppController:
    def __init__(self) -> None:
        self.root = Path.cwd()
        self.config_path = self.root / "config.json"
        self.config = load_config(self.config_path)
        self._ensure_audio_device()
        self.queue: queue.Queue[CaptionUpdate] = queue.Queue()
        self.pipeline: AsrPipeline | None = None
        self.overlay: SubtitleOverlay | None = None
        self._shutting_down = False

    def _ensure_audio_device(self) -> None:
        if self.config.get("audio_monitor"):
            return
        try:
            monitors = list_audio_monitors()
        except Exception:
            return
        if monitors:
            self.config["audio_monitor"] = monitors[0]
            save_config(self.config, self.config_path)

    def start(self) -> int:
        qt_app = QtWidgets.QApplication(sys.argv)
        qt_app.setQuitOnLastWindowClosed(True)

        self.overlay = SubtitleOverlay(
            text_queue=self.queue,
            config=self.config,
            on_open_settings=self.open_settings,
            on_close_app=self.shutdown,
        )
        self.overlay.show()

        try:
            self._start_pipeline()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self.overlay,
                "Error al iniciar ASR",
                f"{exc}\n\nAbre ⚙ y elige dispositivo/modelo, luego Guarda.",
            )

        code = qt_app.exec()
        self.shutdown()
        return code

    def _start_pipeline(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
        self.pipeline = AsrPipeline(self.config, self.queue)
        self.pipeline.start()

    def open_settings(self) -> None:
        assert self.overlay is not None
        dlg = SettingsDialog(self.overlay, self.config)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        new_cfg = dlg.result_config()
        new_cfg["window_pos"] = self.overlay.current_position()
        restart_needed = any(
            new_cfg.get(k) != self.config.get(k)
            for k in ("language", "model", "audio_monitor", "device", "compute_type", "use_vad")
        )
        self.config = new_cfg
        save_config(self.config, self.config_path)
        self.overlay.apply_config(self.config)

        if restart_needed:
            try:
                self._start_pipeline()
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self.overlay, "Error al reiniciar ASR", str(exc))

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if self.overlay is not None:
            self.config["window_pos"] = self.overlay.current_position()
            save_config(self.config, self.config_path)
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
        if self.overlay is not None:
            overlay = self.overlay
            self.overlay = None
            overlay.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()


def main() -> None:
    try:
        controller = AppController()
        raise SystemExit(controller.start())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
