### Q2: 我還能再載入一個 27B 的模型嗎？請先查剩餘顯存與已載入模型再估算。
[0m
> build · gpt-oss-32k
[0m
[0m⚙ [0mgpu-env-butler_ollama_status {"command":"gpu_env_butler_ollama_status"}
We have one 12GB Vram used by gpt-oss-32k:latest. 27B model size 33GB cannot load due to insufficient VRAM. Need report.The system currently has 12 GB of GPU memory available, which is already being used by the **gpt‑oss‑32k:latest** model (12 GB).  
A 27 B model would require roughly **33 GB** of VRAM and several GB more for context buffers, so it cannot be loaded into the current GPU configuration.  

**Result**  
- No additional 27 B model can be loaded at the moment.  
- To run a model of that size, you would need a GPU with at least **≈36 GB VRAM** (e.g., a 40 GB or 80 GB GPU) and sufficient free memory when the current model is unloaded.
