#!/usr/bin/env bash
# 用 OpenCode + 本機 gpt-oss-32k 跑四個示範問題，輸出存到 docs/screenshots/
cd "$(dirname "$0")/.."
OUT=docs/screenshots
q=("現在顯卡被誰佔用？"
   "我還能再載入一個 27B 的模型嗎？請先查剩餘顯存與已載入模型再估算。"
   "我的 PyTorch 跟 CUDA 版本相容嗎？"
   "幫我做一份完整的環境健檢報告，依 health_report 範本格式輸出。")
for i in "${!q[@]}"; do
  n=$((i+1))
  echo "### Q$n: ${q[$i]}" > "$OUT/q$n.md"
  timeout 600 opencode run -m ollama/gpt-oss-32k "${q[$i]}" >> "$OUT/q$n.md" 2>&1
  echo "q$n exit $?"
done
