from __future__ import annotations

import os
import queue
import sys
import traceback
from pathlib import Path

# En GNOME/Wayland, "siempre encima" de Qt suele fallar. XWayland (xcb) sí respeta
# WindowStaysOnTopHint / _NET_WM_STATE_ABOVE, como el menú de Chrome.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PyQt6 import QtWidgets

from src.asr.pipeline import AsrPipeline
from src.asr.types import CaptionUpdate
from src.audio.devices import list_audio_monitors
from src.config import load_config, save_config, validate_config
from src.debug.trace import (
    SessionTracer,
    debug_trace_enabled,
    resolve_trace_path,
)
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
        self._tracer: SessionTracer | None = None
        if debug_trace_enabled():
            self._tracer = SessionTracer(
                resolve_trace_path(self.root), self.config
            )
            print(
                f"[debug] trazas activas → {self._tracer.path}",
                flush=True,
            )

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
            on_save_config=self._save_config,
            on_restart_pipeline=self._restart_pipeline_safe,
            on_translation_changed=self._hot_swap_translator,
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

    def _save_config(
        self,
        cfg: dict | None = None,
        *,
        trace_reason: str = "save",
        trace_applied: str | None = None,
    ) -> None:
        if cfg is not None:
            self.config = cfg
        if self.overlay is not None:
            self.config["window_pos"] = self.overlay.current_position()
            self.config["window_width"] = self.overlay.width()
        if self._tracer is not None and not self._shutting_down:
            self._tracer.note_config(
                self.config, reason=trace_reason, applied=trace_applied
            )
        save_config(self.config, self.config_path)

    def _start_pipeline(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
        self.pipeline = AsrPipeline(
            self.config, self.queue, tracer=self._tracer
        )
        self.pipeline.start()

    def _restart_pipeline_safe(self) -> None:
        assert self.overlay is not None
        try:
            self._start_pipeline()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self.overlay, "Error al reiniciar ASR", str(exc)
            )

    def _hot_swap_translator(self) -> None:
        if self.pipeline is None:
            return
        try:
            self.pipeline.apply_translation_settings(self.config)
        except Exception as exc:
            assert self.overlay is not None
            QtWidgets.QMessageBox.warning(
                self.overlay,
                "Traducción",
                f"No se pudo actualizar el traductor: {exc}\nSe mantiene el ASR.",
            )

    def open_settings(self) -> None:
        assert self.overlay is not None
        dlg = SettingsDialog(self.overlay, self.config)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        new_cfg = validate_config(dlg.result_config())
        new_cfg["window_pos"] = self.overlay.current_position()
        asr_restart_keys = (
            "language",
            "model",
            "audio_monitor",
            "device",
            "compute_type",
            "use_vad",
            "latency_mode",
            "latency_profiles",
        )
        translation_keys = (
            "translation_enabled",
            "translation_target",
            "translation_sticky_mode",
            "translator_model",
            "translation_decode_preset",
            "translation_profiles",
        )
        display_keys = (
            "captions_show_partials",
            "captions_allow_rewrite",
            "second_line_mode",
        )
        asr_restart = any(
            new_cfg.get(k) != self.config.get(k) for k in asr_restart_keys
        )
        translation_only = (not asr_restart) and any(
            new_cfg.get(k) != self.config.get(k) for k in translation_keys
        )
        if asr_restart:
            applied = "asr_restart"
        elif translation_only:
            applied = "translation_hot_swap"
        else:
            applied = "none"
        self.config = new_cfg
        self._save_config(
            self.config, trace_reason="settings", trace_applied=applied
        )
        self.overlay.apply_config(self.config)

        if asr_restart:
            self._restart_pipeline_safe()
        else:
            if translation_only:
                self._hot_swap_translator()
            if self.pipeline is not None:
                for key in display_keys:
                    self.pipeline.config[key] = self.config[key]

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if self.overlay is not None:
            self._save_config()
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
        if self._tracer is not None:
            try:
                path = self._tracer.flush()
                print(f"[debug] trace guardado en {path}", flush=True)
            except Exception as exc:
                print(f"[debug] no se pudo guardar trace: {exc}", flush=True)
            self._tracer = None
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
