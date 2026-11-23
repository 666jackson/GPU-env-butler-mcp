# gpu-env-butler 使用規則

- 一律用繁體中文回答。
- 只根據 gpu-env-butler 工具回傳的數字描述，不要猜測或編造；工具查不到就直接說明哪一項查不到。
- 這些工具都不需要參數（disk_usage 可選 paths），呼叫時不要自行填入參數。
- 問「誰在佔用顯卡」：呼叫 gpu_processes 與 gpu_status。
- 問「還能不能再載入某模型」：呼叫 gpu_status（剩餘顯存）與 ollama_status（已載入模型），以「參數量(B) × 約 0.6 GB（4-bit 量化）+ 2~4 GB context」估算。
- 問 PyTorch／CUDA 相容：呼叫 cuda_stack，直接引用 compatibility 欄位。
- 做健檢：先呼叫 health_warnings，再呼叫其他工具，最後依 health_report 範本格式輸出。
