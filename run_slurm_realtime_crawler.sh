#!/bin/bash
#SBATCH --job-name=sbatch
#SBATCH --partition=gpus
#SBATCH --output=/vol/biomedic3/gn425/HaNoiAQI/logs/out/%x.%N.%j.out
#SBATCH --error=/vol/biomedic3/gn425/HaNoiAQI/logs/err/%x.%N.%j.err

set -euo pipefail

PROJECT_ROOT="/vol/biomedic3/gn425/HaNoiAQI"
APP_DIR="${PROJECT_ROOT}/dashboard"
PYTHON="${APP_DIR}/.venv/bin/python"
OUTPUT="${APP_DIR}/runtime/realtime_history.csv"
HF_REPO_ID="${HF_REPO_ID:-MountainRiver/hanoi-aqi-realtime-history}"

mkdir -p "${PROJECT_ROOT}/logs/out" "${PROJECT_ROOT}/logs/err" "${APP_DIR}/runtime"

cd "${APP_DIR}"

if [[ -z "${HF_TOKEN:-}" && -f "${PROJECT_ROOT}/hf_token.txt" ]]; then
  export HF_TOKEN="$(< "${PROJECT_ROOT}/hf_token.txt")"
fi

echo "Starting Hanoi AQI realtime crawler"
echo "Project: ${PROJECT_ROOT}"
echo "Python: ${PYTHON}"
echo "Output: ${OUTPUT}"
echo "HF dataset: ${HF_REPO_ID}"
if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF token: missing; crawler will only write local CSV"
else
  echo "HF token: present"
fi
echo "Started at: $(date -Is)"

"${PYTHON}" scripts/collect_realtime_history.py \
  --output "${OUTPUT}" \
  --interval-minutes 10 \
  --max-hours 168 \
  --keyword hanoi \
  --hf-repo-id "${HF_REPO_ID}" \
  --create-hf-repo
