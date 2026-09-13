import numpy as np

from src.audio.capture import AudioRingBuffer, ChunkPump


def test_ring_buffer_trims() -> None:
    buf = AudioRingBuffer(max_seconds=1.0, sample_rate=16000)
    buf.write(np.ones(20000, dtype=np.float32))
    assert buf.read_all().size == 16000


def test_chunk_pump_respects_min_interval() -> None:
    buf = AudioRingBuffer(sample_rate=16000)
    buf.write(np.ones(16000, dtype=np.float32))
    pump = ChunkPump(buf, min_chunk_seconds=0.5)
    first = pump.poll()
    assert first is not None
    second = pump.poll()
    assert second is None
