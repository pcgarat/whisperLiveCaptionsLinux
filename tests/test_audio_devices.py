from src.audio.devices import parse_pactl_sources_short

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
