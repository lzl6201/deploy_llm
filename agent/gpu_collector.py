import os
import socket
import subprocess
from typing import Any

try:
    import pynvml

    HAS_PYNVML = True
except Exception:  # pragma: no cover
    HAS_PYNVML = False


def get_hostname() -> str:
    return socket.gethostname()


def get_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _has_nvlink() -> bool:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "nvlink", "--status", "--csv"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return "active" in out.lower() and "link" in out.lower()
    except Exception:
        return False


def _has_infiniband() -> bool:
    if os.name != "nt" and os.path.isdir("/sys/class/infiniband"):
        return True
    try:
        out = subprocess.check_output(
            ["ip", "link"], text=True, stderr=subprocess.DEVNULL
        )
        return "ib0" in out.lower() or ": ib" in out.lower()
    except Exception:
        return False


def _detect_interconnect(gpu_count: int) -> str:
    """互联类型：pcie / nvlink / ib（跨机 TP 仅允许后两者）。"""
    if gpu_count > 1 and _has_nvlink():
        return "nvlink"
    if _has_infiniband():
        return "ib"
    return "pcie"


def collect_node_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "hostname": get_hostname(),
        "ip": get_ip(),
        "driver": "",
        "cuda": "",
        "interconnect": "pcie",
        "gpus": [],
    }
    if HAS_PYNVML:
        _collect_pynvml(info)
    else:
        info["gpus"] = _collect_nvidia_smi()
    info["interconnect"] = _detect_interconnect(len(info["gpus"]))
    return info


def _collect_pynvml(info: dict[str, Any]) -> None:
    pynvml.nvmlInit()
    try:
        info["driver"] = pynvml.nvmlSystemGetDriverVersion().decode()
        cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion()
        info["cuda"] = f"{cuda_ver // 1000}.{(cuda_ver % 1000) // 10}"
        count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            power = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
            gpus.append(
                {
                    "index": i,
                    "name": pynvml.nvmlDeviceGetName(h).decode(),
                    "vram_total_mb": mem.total // (1024 * 1024),
                    "vram_used_mb": mem.used // (1024 * 1024),
                    "utilization": float(util.gpu),
                    "temperature": float(temp),
                    "power_w": power,
                }
            )
        info["gpus"] = gpus
    finally:
        pynvml.nvmlShutdown()


def _collect_nvidia_smi() -> list[dict[str, Any]]:
    cmd = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        out = subprocess.check_output(cmd, text=True)
    except Exception:
        return []

    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            gpus.append(
                {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "vram_total_mb": int(float(parts[2])),
                    "vram_used_mb": int(float(parts[3])),
                    "utilization": float(parts[4]),
                    "temperature": float(parts[5]),
                    "power_w": float(parts[6]),
                }
            )
        except ValueError:
            continue
    return gpus
