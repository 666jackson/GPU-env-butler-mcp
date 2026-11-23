from pathlib import Path
import collectors as c
import rules

FIX = Path(__file__).parent / "fixtures"


def gpu(**kw):
    g = {"index": 0, "memory_used_pct": 10, "memory_free_mib": 20000, "temperature_c": 40, "utilization_pct": 50}
    g.update(kw)
    return {"available": True, "driver_cuda_version": "12.4", "gpus": [g]}


def levels(ws):
    return [w["level"] for w in ws]


def test_vram_levels():
    assert levels(rules.check_gpu(gpu(memory_used_pct=95), None)) == ["critical"]
    assert levels(rules.check_gpu(gpu(memory_used_pct=80), None)) == ["warning"]
    assert rules.check_gpu(gpu(memory_used_pct=50), None) == []


def test_temperature_levels():
    assert levels(rules.check_gpu(gpu(temperature_c=90), None)) == ["critical"]
    assert levels(rules.check_gpu(gpu(temperature_c=80), None)) == ["warning"]
    assert rules.check_gpu(gpu(temperature_c=70), None) == []


def test_idle_process():
    procs = {"processes": [{"pid": 1, "process_name": "python", "used_memory_mib": 2000, "gpu_index": 0}]}
    ws = rules.check_gpu(gpu(utilization_pct=1), procs)
    assert levels(ws) == ["warning"] and "PID 1" in ws[0]["message"]
    assert rules.check_gpu(gpu(utilization_pct=60), procs) == []
    small = {"processes": [{"pid": 1, "process_name": "python", "used_memory_mib": 500, "gpu_index": 0}]}
    assert rules.check_gpu(gpu(utilization_pct=1), small) == []


def test_fixture_two_cards():
    g = {"available": True, "gpus": c.parse_gpu_csv((FIX / "nvidia_smi_gpu.csv").read_text())}
    ws = rules.check_gpu(g, None)
    assert levels(ws) == ["critical", "warning"]  # card 0: VRAM 94% + temp 81


def test_no_gpu():
    assert levels(rules.check_gpu({"available": False, "error": "x"}, None)) == ["info"]


def test_ollama_loaded():
    ws = rules.check_ollama({"loaded": [{"name": "gpt-oss:20b", "vram_gb": 13.5, "expires_at": "t"}]})
    assert "ollama stop gpt-oss:20b" in ws[0]["suggestion"]
    assert rules.check_ollama({"loaded": []}) == []


def test_disk():
    assert levels(rules.check_disk({"disks": [{"path": "/", "free_gb": 10, "free_pct": 50}]})) == ["warning"]
    assert levels(rules.check_disk({"disks": [{"path": "/", "free_gb": 100, "free_pct": 5}]})) == ["warning"]
    assert rules.check_disk({"disks": [{"path": "/", "free_gb": 100, "free_pct": 50}]}) == []


def test_ram_and_load():
    assert levels(rules.check_system({"ram_available_pct": 5})) == ["warning"]
    assert levels(rules.check_system({"ram_available_pct": 50, "load_avg_1_5_15": [20, 1, 1], "cpu_cores_logical": 8})) == ["info"]
    assert rules.check_system({"ram_available_pct": 50, "load_avg_1_5_15": [1, 1, 1], "cpu_cores_logical": 8}) == []


def test_cuda_unavailable():
    ws = rules.check_cuda({"torch_installed": True, "cuda_available": False, "torch_version": "2.3.0+cpu"})
    assert levels(ws) == ["critical"]
    assert rules.check_cuda({"torch_installed": False}) == []


def test_cuda_version_mismatch():
    base = {"torch_installed": True, "cuda_available": True}
    assert levels(rules.check_cuda({**base, "torch_cuda_version": "12.8"}, "11.8")) == ["critical"]
    assert rules.check_cuda({**base, "torch_cuda_version": "12.1"}, "12.4") == []
    assert rules.check_cuda({**base, "torch_cuda_version": "11.8"}, "12.4") == []


def test_python_rules():
    ws = rules.check_python({"conda_env": "base", "packages": {"torch": "2.3", "vllm": "未安裝"}})
    assert levels(ws) == ["info", "info"] and "vllm" in ws[1]["message"]
    assert rules.check_python({"conda_env": "proj", "packages": {"torch": "2.3"}}) == []


def test_evaluate_sorted():
    r = rules.evaluate({"gpu": gpu(memory_used_pct=95), "python": {"conda_env": "base", "packages": {}},
                        "disk": {"disks": [{"path": "/", "free_gb": 5, "free_pct": 50}]}})
    assert levels(r["warnings"]) == ["critical", "warning", "info"]
    assert r["overall"] == "有問題"
