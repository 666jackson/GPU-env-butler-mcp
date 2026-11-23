"""收集 GPU、系統、Python/CUDA 與 Ollama 狀態。全部只讀。

解析函式接受文字輸入（parse_*），方便用 fixture 測試。
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from importlib import metadata

import psutil
import requests

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
KEY_PACKAGES = ["torch", "torchvision", "transformers", "accelerate", "vllm", "openai", "numpy"]
GPU_FIELDS = ["index", "name", "driver_version", "memory_total_mib", "memory_used_mib",
              "memory_free_mib", "utilization_pct", "temperature_c", "power_draw_w"]


def run(cmd, timeout=10):
    """執行外部指令，回傳 (ok, stdout 或錯誤說明)。不會丟例外。"""
    try:
        p = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, f"找不到指令 {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"{cmd[0]} 執行超過 {timeout} 秒"
    if p.returncode != 0:
        return False, (p.stderr or p.stdout).strip() or f"{cmd[0]} 回傳 {p.returncode}"
    return True, p.stdout


def _num(s):
    s = s.strip()
    if not s or s.startswith("[") or s.upper() in ("N/A", "NOT SUPPORTED"):
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


# ---------- GPU ----------

def parse_gpu_csv(text):
    gpus = []
    for line in text.strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < len(GPU_FIELDS):
            continue
        g = dict(zip(GPU_FIELDS, cols))
        for k in GPU_FIELDS[3:]:
            g[k] = _num(g[k])
        g["index"] = _num(g["index"])
        if g["memory_total_mib"] and g["memory_used_mib"] is not None:
            g["memory_used_pct"] = round(g["memory_used_mib"] / g["memory_total_mib"] * 100, 1)
        else:
            g["memory_used_pct"] = None
        gpus.append(g)
    return gpus


def parse_cuda_version(header):
    m = re.search(r"CUDA (?:UMD )?Version:\s*([\d.]+)", header)
    return m.group(1) if m else None


def parse_apps_csv(text):
    apps = []
    for line in text.strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 3:
            continue
        apps.append({"pid": _num(cols[0]), "process_name": cols[1], "used_memory_mib": _num(cols[2])})
    return apps


def gpu_status():
    ok, out = run(["nvidia-smi", "--query-gpu=" + ",".join([
        "index", "name", "driver_version", "memory.total", "memory.used", "memory.free",
        "utilization.gpu", "temperature.gpu", "power.draw"]), "--format=csv,noheader,nounits"])
    if not ok:
        return {"available": False, "error": f"無法取得 GPU 資訊：{out}"}
    ok2, header = run(["nvidia-smi"])
    return {"available": True, "driver_cuda_version": parse_cuda_version(header) if ok2 else None,
            "gpus": parse_gpu_csv(out)}


def gpu_processes():
    ok, out = run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
                   "--format=csv,noheader,nounits"])
    if not ok:
        return {"available": False, "error": f"無法取得 GPU 程式列表：{out}"}
    ok2, uuids = run(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"])
    uuid_to_idx = {}
    if ok2:
        for line in uuids.strip().splitlines():
            i, u = [c.strip() for c in line.split(",")]
            uuid_to_idx[u] = _num(i)
    procs = []
    for line in out.strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 4:
            continue
        p = parse_apps_csv(",".join(cols[1:]))[0]
        p["gpu_index"] = uuid_to_idx.get(cols[0])
        try:
            ps = psutil.Process(p["pid"])
            p["user"] = ps.username()
            p["running_seconds"] = int(time.time() - ps.create_time())
        except Exception:
            p["user"] = None
            p["running_seconds"] = None  # 容器/WSL 下常看不到其他命名空間的程式
        procs.append(p)
    out = {"available": True, "processes": procs}
    if not procs and "microsoft" in platform.release().lower():
        out["note"] = "WSL2 下看不到 Windows 端程式（例如 Windows 版 Ollama），清單為空但顯存仍可能被佔用；請對照 gpu_status 與 ollama_status"
    return out


# ---------- 系統 ----------

def system_info():
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()
    try:
        load = [round(x, 2) for x in os.getloadavg()]
    except OSError:
        load = None
    cpu_model = platform.processor()
    try:
        with open("/proc/cpuinfo") as f:
            m = re.search(r"model name\s*:\s*(.+)", f.read())
            cpu_model = m.group(1) if m else cpu_model
    except OSError:
        pass
    gb = 1024 ** 3
    return {
        "hostname": platform.node(), "os": f"{platform.system()} {platform.release()}",
        "cpu_model": cpu_model, "cpu_cores_logical": psutil.cpu_count(),
        "cpu_cores_physical": psutil.cpu_count(logical=False), "load_avg_1_5_15": load,
        "ram_total_gb": round(vm.total / gb, 1), "ram_available_gb": round(vm.available / gb, 1),
        "ram_available_pct": round(vm.available / vm.total * 100, 1),
        "swap_total_gb": round(sw.total / gb, 1), "swap_used_gb": round(sw.used / gb, 1),
        "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
    }


def disk_usage(paths=None):
    paths = paths or ["~", ".", "~/.ollama"]
    out = []
    for p in paths:
        full = os.path.abspath(os.path.expanduser(p))
        try:
            u = shutil.disk_usage(full)
        except OSError as e:
            out.append({"path": full, "error": f"無法讀取：{e.strerror}"})
            continue
        gb = 1024 ** 3
        out.append({"path": full, "total_gb": round(u.total / gb, 1), "used_gb": round(u.used / gb, 1),
                    "free_gb": round(u.free / gb, 1), "free_pct": round(u.free / u.total * 100, 1)})
    return {"disks": out}


# ---------- Python / CUDA ----------

def python_env():
    pkgs = {}
    for name in KEY_PACKAGES:
        try:
            pkgs[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pkgs[name] = "未安裝"
    envs = None
    ok, out = run(["conda", "env", "list", "--json"], timeout=15)
    if ok:
        try:
            envs = json.loads(out).get("envs")
        except json.JSONDecodeError:
            pass
    return {"python_version": platform.python_version(), "python_path": sys.executable,
            "conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
            "conda_envs": envs if envs is not None else "conda 不可用", "packages": pkgs}


TORCH_PROBE = ("import json,torch;c=torch.cuda.is_available();print(json.dumps({"
               "'torch_version':torch.__version__,'torch_cuda_version':torch.version.cuda,"
               "'cuda_available':c,'device_count':torch.cuda.device_count() if c else 0,"
               "'cudnn_version':torch.backends.cudnn.version() if c else None}))")


def parse_nvcc(text):
    m = re.search(r"release\s+([\d.]+)", text)
    return m.group(1) if m else None


def cuda_stack(python=None):
    """用子程序跑 torch，避免 server 本身 import torch。"""
    info = {"python_used": python or sys.executable}
    ok, out = run([python or sys.executable, "-c", TORCH_PROBE], timeout=30)
    if ok:
        info.update(json.loads(out.strip().splitlines()[-1]))
        info["torch_installed"] = True
    else:
        info["torch_installed"] = False
        info["torch_error"] = "未安裝 torch" if "No module named" in out else out[-300:]
    ok, out = run(["nvcc", "--version"])
    info["nvcc_version"] = parse_nvcc(out) if ok else "未安裝 nvcc"
    ok, header = run(["nvidia-smi"])
    info["driver_cuda_version"] = parse_cuda_version(header) if ok else None
    info["compatibility"] = cuda_compatibility(info)
    return info


def cuda_compatibility(info):
    """程式判斷相容性，避免模型自行推論。驅動 CUDA 版本是上限，向下相容。"""
    drv = info.get("driver_cuda_version")
    if not info.get("torch_installed"):
        return (f"目前 Python 未安裝 torch，無法檢查。驅動支援 CUDA {drv}（上限），"
                f"可安裝 CUDA 主版本 ≤ {drv} 的 PyTorch（例如 cu12x 或 cu13x 版）" if drv else "未安裝 torch，也查不到驅動")
    tc = info.get("torch_cuda_version")
    if tc is None:
        return "安裝的是 CPU 版 PyTorch，無法使用 GPU"
    if drv and int(tc.split(".")[0]) > int(drv.split(".")[0]):
        return f"不相容：torch 用 CUDA {tc} 編譯，但驅動只支援到 CUDA {drv}"
    if not info.get("cuda_available"):
        return f"版本看似可行（torch CUDA {tc}，驅動 {drv}），但 torch.cuda.is_available() 為 False，環境有問題"
    return f"相容：torch CUDA {tc} ≤ 驅動支援的 CUDA {drv}，且 GPU 可用"


# ---------- Ollama ----------

def ollama_status():
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5).json()
        ps = requests.get(f"{OLLAMA_URL}/api/ps", timeout=5).json()
    except requests.RequestException:
        return {"running": False, "error": f"Ollama 未啟動或連不到 {OLLAMA_URL}"}
    gb = 1024 ** 3
    installed = [{"name": m["name"], "size_gb": round(m.get("size", 0) / gb, 1),
                  "params": m.get("details", {}).get("parameter_size")} for m in tags.get("models", [])]
    loaded = [{"name": m["name"], "size_gb": round(m.get("size", 0) / gb, 1),
               "vram_gb": round(m.get("size_vram", 0) / gb, 1),
               "context_length": m.get("context_length"), "expires_at": m.get("expires_at")}
              for m in ps.get("models", [])]
    return {"running": True, "installed": installed, "loaded": loaded}


def collect_all():
    return {"gpu": gpu_status(), "processes": gpu_processes(), "system": system_info(),
            "disk": disk_usage(), "python": python_env(), "cuda": cuda_stack(),
            "ollama": ollama_status()}
