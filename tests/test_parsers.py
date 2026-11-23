from pathlib import Path
import collectors as c

FIX = Path(__file__).parent / "fixtures"


def test_parse_gpu_csv():
    gpus = c.parse_gpu_csv((FIX / "nvidia_smi_gpu.csv").read_text())
    assert len(gpus) == 2
    assert gpus[0]["name"] == "NVIDIA GeForce RTX 4090"
    assert gpus[0]["memory_used_mib"] == 23100
    assert gpus[0]["memory_used_pct"] == 94.0
    assert gpus[0]["power_draw_w"] == 310.25


def test_parse_gpu_na_and_short_rows():
    gpus = c.parse_gpu_csv((FIX / "nvidia_smi_gpu.csv").read_text() + "\n2, broken, row\n")
    assert len(gpus) == 2
    assert gpus[1]["power_draw_w"] is None


def test_parse_apps_csv():
    apps = c.parse_apps_csv((FIX / "nvidia_smi_apps.csv").read_text())
    assert apps[0] == {"pid": 12345, "process_name": "python", "used_memory_mib": 21800}


def test_parse_cuda_and_nvcc():
    assert c.parse_cuda_version("| Driver Version: 550.54  CUDA Version: 12.4 |") == "12.4"
    assert c.parse_cuda_version("nothing") is None
    assert c.parse_nvcc("Cuda compilation tools, release 12.1, V12.1.105") == "12.1"


def test_run_missing_command():
    ok, msg = c.run(["definitely-not-a-cmd-xyz"])
    assert not ok and "找不到" in msg
