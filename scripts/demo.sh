#!/bin/bash
# Demo script: chạy 3 query bắt buộc end-to-end.
# Yêu cầu: server đang chạy (uvicorn main:app --reload), jq + curl.
set -e
BASE=http://localhost:8000/api/v1

poll() {
  local job_id="$1"
  for i in $(seq 1 120); do
    STATUS=$(curl -s "$BASE/jobs/$job_id" | jq -r .status)
    if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ]; then
      break
    fi
    sleep 1
  done
  curl -s "$BASE/jobs/$job_id" | jq .
}

echo "=== 1. pH Scale ==="
JOB1=$(curl -s -X POST "$BASE/jobs" -H "Content-Type: application/json" \
  -d '{"query":"How does the pH scale work?"}' | jq -r .job_id)
echo "Job: $JOB1"
poll "$JOB1"

echo "=== 2. Covalent bonds ==="
JOB2=$(curl -s -X POST "$BASE/jobs" -H "Content-Type: application/json" \
  -d '{"query":"Why do atoms form covalent bonds?"}' | jq -r .job_id)
echo "Job: $JOB2"
poll "$JOB2"

echo "=== 3. Ionic vs Covalent ==="
JOB3=$(curl -s -X POST "$BASE/jobs" -H "Content-Type: application/json" \
  -d '{"query":"What is the difference between ionic and covalent bonding?"}' | jq -r .job_id)
echo "Job: $JOB3"
poll "$JOB3"