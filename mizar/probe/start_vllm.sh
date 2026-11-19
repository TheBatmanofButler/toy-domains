#!/bin/bash
# Starts the model server for the thinking-length probe. The one argument is the folder to work in; the server's
# log is written there as vllm_server.log.
set -e
FOLDER="${1:?usage: start_vllm.sh FOLDER}"
cd "$FOLDER"
exec vllm serve Qwen/Qwen3.8-27B --revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0 --served-model-name Qwen3.8-27B --dtype bfloat16 --host 127.0.0.1 --port 8000 --max-model-len 70000 --reasoning-parser qwen3 --gpu-memory-utilization 0.92 --max-num-seqs 16 --seed 0 > "$FOLDER/vllm_server.log" 2>&1
