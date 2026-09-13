from src.ui.settings import _friendly_audio_label


def test_friendly_audio_bluetooth() -> None:
    assert (
        _friendly_audio_label("bluez_output.44_73_D6_C9_A1_5F.1.monitor")
        == "Bluetooth · 44:73:D6:C9:A1:5F"
    )


def test_friendly_audio_alsa() -> None:
    assert (
        _friendly_audio_label("alsa_output.pci-0000_00_1f.3.analog-stereo.monitor")
        == "Salida ALSA · pci-0000_00_1f.3.analog-stereo"
    )


def test_friendly_audio_empty() -> None:
    assert _friendly_audio_label("") == "(sin dispositivo)"
