"""規則式提醒：判斷交給程式，表達交給模型。門檻集中在最上方。"""

VRAM_CRITICAL_PCT = 90
VRAM_WARNING_PCT = 75
TEMP_CRITICAL_C = 85
TEMP_WARNING_C = 78
IDLE_PROC_MIN_MIB = 1024
IDLE_GPU_UTIL_PCT = 5
DISK_MIN_FREE_PCT = 10
DISK_MIN_FREE_GB = 20
RAM_MIN_AVAILABLE_PCT = 10

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _w(level, message, suggestion):
    return {"level": level, "message": message, "suggestion": suggestion}


def _major(v):
    try:
        return int(str(v).split(".")[0])
    except (ValueError, TypeError):
        return None


def check_gpu(gpu, processes):
    out = []
    if not gpu.get("available"):
        return [_w("info", gpu.get("error", "查不到 GPU"), "確認 NVIDIA 驅動與 nvidia-smi 是否可用")]
    util_by_idx = {}
    for g in gpu.get("gpus", []):
        i, pct, t = g["index"], g.get("memory_used_pct"), g.get("temperature_c")
        util_by_idx[i] = g.get("utilization_pct")
        if pct is not None and pct >= VRAM_CRITICAL_PCT:
            out.append(_w("critical", f"GPU {i} 顯存使用 {pct}%，快滿了，新任務可能 OOM",
                          "先用 gpu_processes 找出佔用者"))
        elif pct is not None and pct >= VRAM_WARNING_PCT:
            out.append(_w("warning", f"GPU {i} 顯存使用 {pct}%，剩餘 {g['memory_free_mib']} MiB",
                          "載入大模型前先確認剩餘顯存"))
        if t is not None and t >= TEMP_CRITICAL_C:
            out.append(_w("critical", f"GPU {i} 溫度 {t}°C 過高", "檢查散熱與風扇"))
        elif t is not None and t >= TEMP_WARNING_C:
            out.append(_w("warning", f"GPU {i} 溫度 {t}°C 偏高", "留意機箱通風"))
    for p in (processes or {}).get("processes", []):
        mem, util = p.get("used_memory_mib"), util_by_idx.get(p.get("gpu_index"))
        if util is None and len(util_by_idx) == 1:
            util = next(iter(util_by_idx.values()))
        if mem and mem >= IDLE_PROC_MIN_MIB and util is not None and util < IDLE_GPU_UTIL_PCT:
            out.append(_w("warning",
                          f"PID {p['pid']}（{p['process_name']}，使用者 {p.get('user') or '未知'}）"
                          f"佔用 {mem} MiB 但該卡使用率只有 {util}%，可能是閒置程式",
                          "確認是否為忘記關的 notebook kernel，再決定是否關閉"))
    return out


def check_ollama(ollama):
    return [_w("info", f"Ollama 已載入 {m['name']}，佔 {m['vram_gb']} GB 顯存，卸載時間 {m.get('expires_at')}",
               f"不用時可執行 ollama stop {m['name']} 釋放顯存")
            for m in (ollama or {}).get("loaded", [])]


def check_disk(disk):
    out = []
    for d in (disk or {}).get("disks", []):
        if "free_gb" in d and (d["free_pct"] < DISK_MIN_FREE_PCT or d["free_gb"] < DISK_MIN_FREE_GB):
            out.append(_w("warning", f"{d['path']} 剩餘 {d['free_gb']} GB（{d['free_pct']}%），空間不足",
                          "下載模型或存 checkpoint 前先清理"))
    return out


def check_system(sysinfo):
    out = []
    if not sysinfo:
        return out
    if sysinfo.get("ram_available_pct") is not None and sysinfo["ram_available_pct"] < RAM_MIN_AVAILABLE_PCT:
        out.append(_w("warning", f"RAM 可用只剩 {sysinfo['ram_available_pct']}%，記憶體吃緊",
                      "關閉不需要的程式或降低 batch size"))
    load, cores = sysinfo.get("load_avg_1_5_15"), sysinfo.get("cpu_cores_logical")
    if load and cores and load[0] > cores:
        out.append(_w("info", f"1 分鐘負載 {load[0]} 高於核心數 {cores}，CPU 忙碌", "用 top 或 htop 查看"))
    return out


def check_cuda(cuda, driver_cuda=None):
    out = []
    if not cuda or not cuda.get("torch_installed"):
        return out
    if not cuda.get("cuda_available"):
        out.append(_w("critical", f"已安裝 torch {cuda.get('torch_version')} 但 torch.cuda.is_available() 為 False",
                      "可能裝到 CPU 版 PyTorch 或 CUDA 環境有問題；到 pytorch.org 依驅動版本重裝"))
    tm, dm = _major(cuda.get("torch_cuda_version")), _major(driver_cuda or cuda.get("driver_cuda_version"))
    if tm is not None and dm is not None and tm > dm:
        out.append(_w("critical", f"PyTorch 用 CUDA {cuda['torch_cuda_version']} 編譯，但驅動只支援 CUDA "
                      f"{driver_cuda or cuda.get('driver_cuda_version')}",
                      "升級 NVIDIA 驅動，或改裝對應較舊 CUDA 版本的 PyTorch"))
    return out


def check_python(py):
    out = []
    if not py:
        return out
    if py.get("conda_env") == "base":
        out.append(_w("info", "目前在 conda base 環境", "建議為每個專案建立獨立環境：conda create -n 專案名 python=3.11"))
    missing = [k for k, v in py.get("packages", {}).items() if v == "未安裝"]
    if missing:
        out.append(_w("info", f"目前環境未安裝：{', '.join(missing)}", "需要時再用 pip install 安裝"))
    return out


def evaluate(data):
    gpu = data.get("gpu", {})
    warnings = (check_gpu(gpu, data.get("processes")) + check_ollama(data.get("ollama"))
                + check_disk(data.get("disk")) + check_system(data.get("system"))
                + check_cuda(data.get("cuda"), gpu.get("driver_cuda_version"))
                + check_python(data.get("python")))
    warnings.sort(key=lambda w: LEVEL_ORDER[w["level"]])
    counts = {lv: sum(w["level"] == lv for w in warnings) for lv in LEVEL_ORDER}
    status = "有問題" if counts["critical"] else "需要注意" if counts["warning"] else "健康"
    return {"overall": status, "counts": counts, "warnings": warnings}
