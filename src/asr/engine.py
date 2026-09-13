from __future__ import annotations

import numpy as np


class WhisperEngine:
    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "en",
        use_vad: bool = True,
        beam_size: int = 5,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.use_vad = use_vad
        self.beam_size = beam_size
        self._model = None

    def load(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Falta faster-whisper. Activa el venv e instala requirements.txt."
            ) from exc

        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as exc:
            if self.device == "cuda":
                raise RuntimeError(
                    "No se pudo inicializar CUDA para faster-whisper. "
                    "Revisa drivers NVIDIA / ctranslate2. "
                    f"Detalle: {exc}"
                ) from exc
            raise

    def transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            raise RuntimeError("El modelo ASR no está cargado. Llama a load() antes.")

        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            task="transcribe",
            vad_filter=self.use_vad,
            beam_size=self.beam_size,
            condition_on_previous_text=True,
            without_timestamps=True,
        )
        return " ".join(
            seg.text.strip() for seg in segments if seg.text.strip()
        ).strip()
