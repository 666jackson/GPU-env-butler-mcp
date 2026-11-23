"""gpu-env-butler：只讀的 GPU 與環境管家 MCP server。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402

import collectors as c  # noqa: E402
import rules  # noqa: E402

mcp = FastMCP("gpu-env-butler")


def _j(obj):
    return json.dumps(obj, ensure_ascii=False)


@mcp.tool()
def gpu_status() -> str:
    """查看每張 GPU 的型號、顯存總量/已用/剩餘(MiB)、使用率、溫度、功耗與驅動支援的 CUDA 版本。問顯卡狀態或剩多少顯存時用。"""
    return _j(c.gpu_status())


@mcp.tool()
def gpu_processes() -> str:
    """列出正在用 GPU 的程式：PID、名稱、使用者、佔用顯存(MiB)、已執行時間。問「顯卡被誰佔用」時用。"""
    return _j(c.gpu_processes())


@mcp.tool()
def system_info() -> str:
    """查看作業系統、CPU 型號與核心數、負載、RAM 與 swap、開機時間。問 CPU 或系統記憶體時用。"""
    return _j(c.system_info())


@mcp.tool()
def disk_usage(paths: list[str] | None = None) -> str:
    """查看硬碟剩餘空間(GB 與 %)。預設檢查家目錄、目前資料夾、~/.ollama；可傳入其他路徑。問硬碟空間時用。"""
    return _j(c.disk_usage(paths))


@mcp.tool()
def python_env() -> str:
    """查看 Python 版本與路徑、目前與所有 conda 環境、關鍵套件(torch、transformers 等)版本。問 Python 環境或套件時用。"""
    return _j(c.python_env())


@mcp.tool()
def cuda_stack() -> str:
    """查看 PyTorch 編譯的 CUDA 版本、torch.cuda 是否可用、cuDNN、nvcc 與驅動支援的 CUDA 版本。問 PyTorch 與 CUDA 是否相容時用。"""
    return _j(c.cuda_stack())


@mcp.tool()
def ollama_status() -> str:
    """查看 Ollama 已安裝的模型與大小、目前載入記憶體的模型、各佔多少顯存與卸載時間。問本機 LLM 模型時用。"""
    return _j(c.ollama_status())


@mcp.tool()
def health_warnings() -> str:
    """依固定門檻檢查 GPU、記憶體、硬碟、PyTorch 與 CUDA 相容性，回傳依嚴重程度排序的提醒清單。做健檢或問有沒有問題時優先使用。"""
    return _j(rules.evaluate(c.collect_all()))


HEALTH_REPORT_PROMPT = """請幫我做一份環境健檢報告。

1. 依序呼叫工具：health_warnings、gpu_status、gpu_processes、ollama_status、python_env、cuda_stack、system_info、disk_usage
2. 用繁體中文輸出以下格式：

## 一句話總結
（整體狀態：健康／需要注意／有問題）

## GPU 狀況
（每張卡的顯存、使用率、溫度，誰在用）

## 環境狀況
（Python、conda 環境、PyTorch 與 CUDA 是否相容、關鍵套件）

## 系統資源
（CPU、RAM、硬碟）

## 提醒（依嚴重程度排序）
- 🔴 critical：……（建議做法）
- 🟡 warning：……
- 🔵 info：……

## 下一步建議
（最多三點，具體可執行）

3. 只根據工具回傳的數字描述，不要猜測；工具回報失敗時直接說明哪一項查不到。
"""


@mcp.prompt()
def health_report() -> str:
    """產生完整的環境健檢報告。"""
    return HEALTH_REPORT_PROMPT


if __name__ == "__main__":
    mcp.run()
