from __future__ import annotations

import pytest

from src.audio.backends import AudioBackend, AudioSource, AudioStream
from src.audio.capture import AudioRingBuffer
from src.audio.devices import (
    available_backends,
    describe_audio_source,
    list_audio_sources,
    registered_backends,
    resolve_backend,
)
from src.audio.pulse import (
    PulseBackend,
    friendly_pulse_label,
    parse_pactl_sources_short,
)

SAMPLE = """
58\talsa_input.pci-0000_00_1f.3.analog-stereo\t...
59\talasa_output.pci-0000_00_1f.3.analog-stereo.monitor\t...
60\tbluez_output.AA_BB.1.monitor\t...
""".replace("alasa", "alsa")


def test_parse_prefers_monitors() -> None:
    names = parse_pactl_sources_short(SAMPLE)
    assert names == [
        "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor",
        "bluez_output.AA_BB.1.monitor",
    ]


def test_parse_falls_back_to_all_sources() -> None:
    raw = "1\tmic_only\tmodule-alsa-source.c\n2\tother_mic\tmodule-alsa-source.c\n"
    assert parse_pactl_sources_short(raw) == ["mic_only", "other_mic"]


def test_parse_empty() -> None:
    assert parse_pactl_sources_short("") == []


def test_friendly_audio_bluetooth() -> None:
    assert (
        friendly_pulse_label("bluez_output.44_73_D6_C9_A1_5F.1.monitor")
        == "Bluetooth · 44:73:D6:C9:A1:5F"
    )


def test_friendly_audio_alsa() -> None:
    assert (
        friendly_pulse_label("alsa_output.pci-0000_00_1f.3.analog-stereo.monitor")
        == "Salida ALSA · pci-0000_00_1f.3.analog-stereo"
    )


def test_friendly_audio_empty() -> None:
    assert friendly_pulse_label("") == "(sin dispositivo)"


def test_pulse_describe_marks_loopback() -> None:
    backend = PulseBackend()
    monitor = backend.describe("alsa_output.pci.analog-stereo.monitor")
    assert monitor.is_loopback is True
    assert monitor.backend == "pulse"
    assert monitor.label == "Salida ALSA · pci.analog-stereo"
    mic = backend.describe("alsa_input.pci.analog-stereo")
    assert mic.is_loopback is False


def test_pulse_backend_satisfies_protocol() -> None:
    assert isinstance(PulseBackend(), AudioBackend)


class _FakeStream:
    def __init__(self, buffer: AudioRingBuffer) -> None:
        self.buffer = buffer
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self, timeout: float = 2.0) -> None:
        del timeout
        self._running = False


class _FakeBackend:
    """Backend de mentira: el contrato debe poder cumplirse sin tocar el sistema."""

    name = "fake"

    def is_available(self) -> bool:
        return True

    def list_sources(self) -> list[AudioSource]:
        return [
            AudioSource(id="fake-out", label="Salida falsa", backend=self.name,
                        is_loopback=True)
        ]

    def describe(self, source_id: str) -> AudioSource:
        return AudioSource(
            id=source_id, label=source_id, backend=self.name, is_loopback=False
        )

    def open_stream(
        self,
        source_id: str,
        *,
        buffer: AudioRingBuffer,
        sample_rate: int = 16000,
    ) -> AudioStream:
        del source_id, sample_rate
        return _FakeStream(buffer)


def test_fake_backend_satisfies_protocols() -> None:
    backend = _FakeBackend()
    assert isinstance(backend, AudioBackend)
    stream = backend.open_stream("fake-out", buffer=AudioRingBuffer())
    assert isinstance(stream, AudioStream)
    assert not stream.running
    stream.start()
    assert stream.running
    stream.stop()
    assert not stream.running


def test_registry_helpers_accept_injected_backend() -> None:
    backend = _FakeBackend()
    assert list_audio_sources(backend)[0].id == "fake-out"
    assert describe_audio_source("lo-que-sea", backend).backend == "fake"


def test_resolve_backend_by_name_and_unknown() -> None:
    assert resolve_backend("pulse").name == "pulse"
    with pytest.raises(RuntimeError, match="desconocido"):
        resolve_backend("wasapi")


def test_resolve_backend_without_any_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.audio.devices.available_backends", lambda: [])
    with pytest.raises(RuntimeError, match="pactl"):
        resolve_backend()


def test_registry_contains_only_valid_backends() -> None:
    assert registered_backends()
    for backend in registered_backends():
        assert isinstance(backend, AudioBackend)
    assert all(backend in registered_backends() for backend in available_backends())
