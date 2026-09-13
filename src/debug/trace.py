from __future__ import annotations

import json
import math
import os
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# Knobs útiles para diagnosticar fluidez / latencia (sin UI cosmética).
_CONFIG_KEYS = (
    "language",
    "model",
    "compute_type",
    "device",
    "audio_monitor",
    "buffer_trimming_sec",
    "use_vad",
    "latency_mode",
    "latency_profiles",
    "translation_enabled",
    "translation_target",
    "translation_sticky_mode",
    "translator_model",
    "translation_decode_preset",
    "translation_profiles",
    "second_line_mode",
    "captions_show_partials",
    "captions_allow_rewrite",
)

_TEXT_PREVIEW = 160
_MAX_EVENTS = 100_000


def default_trace_path(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / "debug" / "trace.json"


def debug_trace_enabled() -> bool:
    raw = (os.environ.get("WLCL_DEBUG_TRACE") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def resolve_trace_path(root: Path | None = None) -> Path:
    override = (os.environ.get("WLCL_DEBUG_TRACE_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return default_trace_path(root)


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = rank - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    ordered = sorted(values)
    mean = sum(ordered) / len(ordered)
    return {
        "count": len(ordered),
        "mean_ms": round(mean, 3),
        "p50_ms": round(_percentile(ordered, 50) or 0.0, 3),
        "p95_ms": round(_percentile(ordered, 95) or 0.0, 3),
        "max_ms": round(ordered[-1], 3),
    }


def _preview(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= _TEXT_PREVIEW:
        return cleaned
    return cleaned[: _TEXT_PREVIEW - 1] + "…"


def config_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _CONFIG_KEYS:
        if key in config:
            out[key] = deepcopy(config[key])
    return out


def diff_config(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Diff de knobs de tuning: {clave: {from, to}}."""
    keys = set(before) | set(after)
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(keys):
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changes[key] = {"from": deepcopy(old), "to": deepcopy(new)}
    return changes


class SessionTracer:
    """Acumula eventos de pipeline y vuelca un JSON al cerrar."""

    def __init__(
        self,
        path: Path,
        config: dict[str, Any] | None = None,
        *,
        wall_start: datetime | None = None,
        mono_start: float | None = None,
    ) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._wall_start = wall_start or datetime.now(timezone.utc)
        self._mono_start = mono_start if mono_start is not None else time.monotonic()
        snap = config_snapshot(config or {})
        self._config_initial = deepcopy(snap)
        self._config = snap
        self._events: list[dict[str, Any]] = []
        self._truncated = False
        self._commit_ts: dict[int, float] = {}
        self._asr_infer_ms: list[float] = []
        self._asr_rtf: list[float] = []
        self._tx_decode_ms: list[float] = []
        self._tx_lag_ms: list[float] = []
        self._coalesce_skips = 0
        self._commits = 0
        self._partials = 0
        self._tx_emits = 0
        self._asr_errors = 0
        self._buffer_trims = 0
        self._config_change_count = 0
        self._closed = False

    def record(self, event_type: str, **fields: Any) -> None:
        now = time.monotonic()
        with self._lock:
            if self._closed:
                return
            if len(self._events) >= _MAX_EVENTS:
                self._truncated = True
                return
            event: dict[str, Any] = {
                "t_rel_ms": round((now - self._mono_start) * 1000.0, 3),
                "type": event_type,
            }
            for key, value in fields.items():
                if value is not None:
                    event[key] = value
            self._events.append(event)

    def asr_infer(
        self,
        *,
        audio_sec: float,
        infer_ms: float,
        hyp_len: int,
        hyp_preview: str | None = None,
    ) -> None:
        rtf = (infer_ms / 1000.0) / audio_sec if audio_sec > 0 else None
        with self._lock:
            self._asr_infer_ms.append(float(infer_ms))
            if rtf is not None:
                self._asr_rtf.append(float(rtf))
        self.record(
            "asr_infer",
            audio_sec=round(audio_sec, 4),
            infer_ms=round(infer_ms, 3),
            rtf=round(rtf, 4) if rtf is not None else None,
            hyp_len=hyp_len,
            hyp=_preview(hyp_preview),
        )

    def asr_error(self, message: str) -> None:
        with self._lock:
            self._asr_errors += 1
        self.record("asr_error", message=_preview(message) or "")

    def note_config(
        self,
        config: dict[str, Any],
        *,
        reason: str = "save",
        applied: str | None = None,
    ) -> bool:
        """Registra cambios de knobs respecto al último snapshot conocido."""
        new_snap = config_snapshot(config)
        with self._lock:
            if self._closed:
                return False
            changes = diff_config(self._config, new_snap)
            if not changes:
                return False
            self._config = new_snap
            self._config_change_count += 1
        self.record(
            "config_change",
            reason=reason,
            applied=applied,
            keys=sorted(changes.keys()),
            changes=changes,
        )
        return True

    def commit(
        self, *, seq: int, text: str, is_extension: bool, ts_mono: float | None = None
    ) -> None:
        stamp = ts_mono if ts_mono is not None else time.monotonic()
        with self._lock:
            self._commits += 1
            self._commit_ts[seq] = stamp
        self.record(
            "commit",
            seq=seq,
            chars=len(text),
            is_extension=is_extension,
            text=_preview(text),
        )

    def partial(self, *, seq: int, text: str) -> None:
        with self._lock:
            self._partials += 1
        self.record("partial", seq=seq, chars=len(text), text=_preview(text))

    def tx_schedule(
        self,
        *,
        seq: int,
        gen: int,
        is_partial: bool,
        chars: int,
        coalesced_prev_gen: int | None = None,
    ) -> None:
        if coalesced_prev_gen is not None:
            with self._lock:
                self._coalesce_skips += 1
            self.record(
                "tx_coalesce_skip",
                seq=seq,
                dropped_gen=coalesced_prev_gen,
                kept_gen=gen,
                is_partial=is_partial,
            )
        self.record(
            "tx_schedule",
            seq=seq,
            gen=gen,
            is_partial=is_partial,
            chars=chars,
        )

    def tx_done(
        self,
        *,
        seq: int,
        gen: int,
        decode_ms: float,
        chars_in: int,
        chars_out: int | None,
        is_partial: bool,
        reused_checkpoint: bool = False,
        ts_mono: float | None = None,
    ) -> None:
        stamp = ts_mono if ts_mono is not None else time.monotonic()
        lag_ms: float | None = None
        with self._lock:
            self._tx_decode_ms.append(float(decode_ms))
            self._tx_emits += 1
            commit_ts = self._commit_ts.get(seq)
            if commit_ts is not None:
                lag_ms = max(0.0, (stamp - commit_ts) * 1000.0)
                self._tx_lag_ms.append(lag_ms)
        self.record(
            "tx_done",
            seq=seq,
            gen=gen,
            decode_ms=round(decode_ms, 3),
            lag_ms=round(lag_ms, 3) if lag_ms is not None else None,
            chars_in=chars_in,
            chars_out=chars_out,
            is_partial=is_partial,
            reused_checkpoint=reused_checkpoint,
        )

    def buffer_trim(self, *, keep_sec: float) -> None:
        with self._lock:
            self._buffer_trims += 1
        self.record("buffer_trim", keep_sec=round(keep_sec, 3))

    def build_document(self, *, ended: bool = True) -> dict[str, Any]:
        wall_end = datetime.now(timezone.utc) if ended else None
        mono_end = time.monotonic()
        with self._lock:
            duration = mono_end - self._mono_start
            summary = {
                "duration_sec": round(duration, 3),
                "events": len(self._events),
                "truncated": self._truncated,
                "commits": self._commits,
                "partials": self._partials,
                "tx_emits": self._tx_emits,
                "coalesce_skips": self._coalesce_skips,
                "asr_errors": self._asr_errors,
                "buffer_trims": self._buffer_trims,
                "config_changes": self._config_change_count,
                "asr_infer": _stats(list(self._asr_infer_ms)),
                "asr_rtf": {
                    "count": len(self._asr_rtf),
                    "mean": round(sum(self._asr_rtf) / len(self._asr_rtf), 4)
                    if self._asr_rtf
                    else None,
                    "p50": round(_percentile(sorted(self._asr_rtf), 50) or 0.0, 4)
                    if self._asr_rtf
                    else None,
                    "p95": round(_percentile(sorted(self._asr_rtf), 95) or 0.0, 4)
                    if self._asr_rtf
                    else None,
                    "max": round(max(self._asr_rtf), 4) if self._asr_rtf else None,
                },
                "tx_decode": _stats(list(self._tx_decode_ms)),
                "tx_lag": _stats(list(self._tx_lag_ms)),
            }
            doc = {
                "schema_version": SCHEMA_VERSION,
                "started_at": self._wall_start.isoformat(),
                "ended_at": wall_end.isoformat() if wall_end else None,
                "config": deepcopy(self._config_initial),
                "config_final": deepcopy(self._config),
                "summary": summary,
                "events": list(self._events),
            }
        return doc

    def flush(self) -> Path:
        doc = self.build_document(ended=True)
        with self._lock:
            self._closed = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        tmp.replace(self.path)
        return self.path
