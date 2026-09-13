from __future__ import annotations

import ctypes
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class VramInfo:
    used_mb: float
    total_mb: float


_lock = threading.Lock()
_nvml = None
_nvml_failed = False
_device = None


def _load_nvml() -> bool:
    global _nvml, _nvml_failed, _device
    with _lock:
        if _nvml_failed:
            return False
        if _nvml is not None:
            return True
        try:
            lib = ctypes.CDLL("libnvidia-ml.so.1")
        except OSError:
            _nvml_failed = True
            return False

        lib.nvmlInit_v2.restype = ctypes.c_int
        lib.nvmlShutdown.restype = ctypes.c_int
        lib.nvmlDeviceGetHandleByIndex_v2.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.nvmlDeviceGetHandleByIndex_v2.restype = ctypes.c_int
        lib.nvmlDeviceGetMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.nvmlDeviceGetMemoryInfo.restype = ctypes.c_int

        if lib.nvmlInit_v2() != 0:
            _nvml_failed = True
            return False

        handle = ctypes.c_void_p()
        if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
            lib.nvmlShutdown()
            _nvml_failed = True
            return False

        _nvml = lib
        _device = handle
        return True


class _NvmlMemory(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


def query_vram() -> VramInfo | None:
    """VRAM GPU 0 vía NVML. Safe para llamar desde el hilo UI (~1 Hz)."""
    if not _load_nvml():
        return None
    assert _nvml is not None and _device is not None
    mem = _NvmlMemory()
    with _lock:
        rc = _nvml.nvmlDeviceGetMemoryInfo(_device, ctypes.byref(mem))
    if rc != 0:
        return None
    return VramInfo(
        used_mb=float(mem.used) / (1024.0 * 1024.0),
        total_mb=float(mem.total) / (1024.0 * 1024.0),
    )
