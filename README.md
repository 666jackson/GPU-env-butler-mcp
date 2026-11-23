# gpu-env-butler：GPU 與環境管家（MCP server）

一個**只讀**的 MCP server，讓 AI agent 查詢這台機器的 GPU、系統資源、Python／CUDA 環境與 Ollama 模型狀態，接上 **OpenCode** 後用本機 Ollama 模型（`gpt-oss:20b`，約 14GB 顯存，控制在 20GB 內）回答「幫我做環境健檢」、「我還能再載入一個 27B 模型嗎？」這類問題。

> 展示素材：`docs/screenshots/`（含工具實測輸出 `mcp_tools_output.txt` 與 OpenCode 問答紀錄）

## 它能回答什麼

| 問題 | agent 會呼叫的工具 |
| --- | --- |
| 現在顯卡被誰佔用？ | `gpu_processes`、`gpu_status` |
| 我還能再載入一個 27B 的模型嗎？ | `gpu_status`（剩餘顯存）+ `ollama_status`（已載入模型）→ 估算 |
| 我的 PyTorch 跟 CUDA 版本相容嗎？ | `cuda_stack`、`python_env` |
| 幫我做一份環境健檢 | `health_report` prompt → 依序呼叫全部工具 |

## 架構

```
OpenCode (Host) ──> MCP Client ──stdio──> gpu-env-butler (server.py)
                                              ├─ collectors.py ─> nvidia-smi / psutil / conda / Ollama API
                                              └─ rules.py      ─> 固定門檻 → 提醒清單
```

## 八個工具與一個 prompt

| 名稱 | 類型 | 內容 |
| --- | --- | --- |
| `gpu_status` | Tool | 每張卡型號、driver、驅動支援 CUDA、顯存總量／已用／剩餘 MiB、使用率、溫度、功耗 |
| `gpu_processes` | Tool | 用 GPU 的程式：PID、名稱、使用者、顯存 MiB、執行時間 |
| `system_info` | Tool | OS、CPU、負載、RAM、swap、開機時間 |
| `disk_usage` | Tool | 指定路徑剩餘空間（預設 `~`、`.`、`~/.ollama`） |
| `python_env` | Tool | Python 版本、conda 環境、關鍵套件版本 |
| `cuda_stack` | Tool | torch 的 CUDA 版本、`cuda.is_available()`、cuDNN、nvcc、驅動 CUDA（子程序跑 torch，server 不 import torch） |
| `ollama_status` | Tool | 已安裝／已載入模型、佔用顯存、context、卸載時間 |
| `health_warnings` | Tool | 套用 `rules.py` 門檻，回傳依嚴重程度排序的提醒 |
| `health_report` | Prompt | 固定格式的繁中健檢報告範本 |

## 設計重點

- **全部只讀**：不殺程式、不改設定、不裝套件，只回報狀態與「建議指令」，由人決定。
- **外部指令安全**：一律 `subprocess.run([...], shell=False, timeout=10)`；指令不存在、逾時或失敗時回傳說明字串，server 不會崩潰（沒 GPU、沒 Ollama、沒 torch 都能正常回應）。
- **判斷交給程式，表達交給模型**：小模型讀一堆數字容易漏報，所以顯存 ≥90%、溫度 ≥85°C、torch CUDA 主版本 > 驅動 CUDA 主版本等門檻寫在 `rules.py`（常數集中在檔案最上方），保證一定會出現；模型只負責講成人話。
- **工具描述影響選工具**：docstring 寫清楚「什麼情況該用」，彼此不重疊。改寫前後對照見下方〈工具描述調整紀錄〉。

## 怎麼執行

```bash
conda create -n gpu-butler python=3.11 -y && conda activate gpu-butler
pip install -r requirements.txt          # 注意 mcp<2：mcp 2.x 把 FastMCP 改名為 MCPServer
pytest -q                                # 不需要 GPU / Ollama
python scripts/smoke_client.py           # 用 MCP stdio client 呼叫全部工具
mcp dev server.py                        # 或用 MCP Inspector 在瀏覽器測試

# 建 32K context 模型（OpenCode 系統提示很長）
ollama pull gpt-oss:20b
ollama create gpt-oss-32k -f ollama/gpt-oss-32k.Modelfile

# 在專案根目錄啟動 OpenCode（讀取 opencode.json）
npm i -g opencode-ai && opencode
```

## 遇到的問題（實際紀錄）

1. **新版 nvidia-smi 標頭格式變了**：驅動 610 起標頭是 `CUDA UMD Version: 13.3`，不是 `CUDA Version:`，原本的正則抓不到 → 放寬為 `CUDA (?:UMD )?Version:` 並加測試。
2. **mcp 2.x 不相容**：`mcp.server.fastmcp` 在 2.x 被移除（改名 `MCPServer`），server 一啟動就斷線 → `requirements.txt` 鎖 `mcp<2`。
3. **WSL + Windows Ollama**：Ollama 跑在 Windows 端，模型存在 Windows 磁碟，`~/.ollama` 在 WSL 裡不存在 → `disk_usage` 回報「無法讀取」而不是崩潰。
4. **WSL 看不到 GPU 程式**：WSL2 下 `nvidia-smi --query-compute-apps` 常回傳空清單（Windows 端程式不在 Linux 命名空間），所以 `gpu_processes` 為空但顯存有被使用是正常的。

## 工具描述調整紀錄

<!-- OPENCODE_NOTES -->

## 已知限制與下一步

- 只支援 NVIDIA（nvidia-smi）、單機。
- 可擴充成多台主機監控，或把 `collect_all()` 匯出成 Prometheus metrics。
