from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class StreamingResult:
    partial: str
    committed: str
    newly_committed: str


class LocalAgreementStreamer:
    """Confirma prefijos que se repiten en `agreement_n` hipótesis consecutivas."""

    def __init__(
        self,
        agreement_n: int = 2,
        max_latency_sec: float = 3.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.agreement_n = max(1, int(agreement_n))
        self.max_latency_sec = max(0.2, float(max_latency_sec))
        self._clock = clock or time.monotonic
        self._hypotheses: list[str] = []
        self._committed = ""
        self._pending_since: float | None = None

    @property
    def committed(self) -> str:
        return self._committed

    def reset(self) -> None:
        self._hypotheses.clear()
        self._committed = ""
        self._pending_since = None

    def push(self, hypothesis: str) -> StreamingResult:
        text = _normalize(hypothesis)
        if not text:
            return StreamingResult(
                partial="", committed=self._committed, newly_committed=""
            )

        self._hypotheses.append(text)
        if len(self._hypotheses) > self.agreement_n:
            self._hypotheses = self._hypotheses[-self.agreement_n :]

        newly = self._try_agree()
        newly = self._maybe_force_commit(text, newly) or newly

        latest = self._hypotheses[-1]
        if latest.startswith(self._committed):
            partial = latest[len(self._committed) :].strip()
        else:
            partial = latest

        if partial:
            if self._pending_since is None:
                self._pending_since = self._clock()
        else:
            self._pending_since = None

        return StreamingResult(
            partial=partial,
            committed=self._committed,
            newly_committed=newly,
        )

    def _try_agree(self) -> str:
        newly = ""
        if len(self._hypotheses) < self.agreement_n:
            return newly

        window = self._hypotheses[-self.agreement_n :]
        agreed = _safe_commit_prefix(_common_prefix(window), window)
        if len(agreed) > len(self._committed) and agreed.startswith(self._committed):
            newly = agreed[len(self._committed) :].strip()
            self._committed = agreed.strip()
        elif not self._committed and agreed:
            newly = agreed.strip()
            self._committed = agreed.strip()
        return newly

    def _maybe_force_commit(self, latest: str, newly: str) -> str:
        if newly:
            return ""
        if self._pending_since is None:
            return ""
        if self._clock() - self._pending_since < self.max_latency_sec:
            return ""

        forced = _safe_commit_prefix(latest, [latest]) or latest
        if not forced:
            return ""

        if forced.startswith(self._committed) and len(forced) > len(self._committed):
            delta = forced[len(self._committed) :].strip()
            self._committed = forced.strip()
            self._pending_since = None
            return delta

        if forced != self._committed:
            self._committed = forced.strip()
            self._pending_since = None
            return self._committed
        return ""


def _normalize(text: str) -> str:
    return " ".join(text.strip().split())


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    prefix = strings[0]
    for item in strings[1:]:
        max_len = min(len(prefix), len(item))
        i = 0
        while i < max_len and prefix[i] == item[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix


def _safe_commit_prefix(prefix: str, hypotheses: list[str]) -> str:
    """Evita confirmar a mitad de palabra; conserva palabras completas acordadas."""
    if not prefix:
        return ""

    cut_mid_word = False
    for hyp in hypotheses:
        if not hyp.startswith(prefix):
            continue
        rest = hyp[len(prefix) :]
        if not rest:
            continue
        if prefix[-1].isalnum() and rest[0].isalnum():
            cut_mid_word = True
            break

    if not cut_mid_word:
        return prefix.rstrip()

    if " " not in prefix:
        return ""
    return prefix.rsplit(" ", 1)[0].rstrip()
