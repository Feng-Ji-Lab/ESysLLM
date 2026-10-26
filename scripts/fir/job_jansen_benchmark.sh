#!/bin/bash
#SBATCH --job-name=jansen_marker
#SBATCH --account=def-fji_gpu
#SBATCH --gpus-per-node=nvidia_h100_80gb_hbm3_1g.10gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=23:59:00
#SBATCH --output=%x-%j.out
#
# Marker conversion of one Jansen-benchmark sub-corpus.
#
# Submit with `BENCH=<bench>` set, e.g.:
#   BENCH=hien2024 sbatch --job-name=jansen_marker_hien2024 scripts/job_jansen_benchmark.sh
#   BENCH=ng2023   sbatch --job-name=jansen_marker_ng2023   scripts/job_jansen_benchmark.sh
#   BENCH=vu2024   sbatch --job-name=jansen_marker_vu2024   scripts/job_jansen_benchmark.sh
#
# All three are independent; you can sbatch them in any order or in parallel.
# The coordinator skips already-completed PDFs, so a timed-out job can be
# resubmitted to resume.

set -e

if [ -z "${BENCH:-}" ]; then
  echo "Set BENCH env var to one of: hien2024 ng2023 vu2024" >&2
  exit 1
fi

case "$BENCH" in
  hien2024|ng2023|vu2024|bennett2023|bowes2023|buecker2023) ;;
  *)
    echo "Unknown BENCH=$BENCH (must be hien2024 / ng2023 / vu2024)" >&2
    exit 1
    ;;
esac

module load python/3.11
source venv/bin/activate
export VERTEX_LOCATION=us-west1
export GOOGLE_CLOUD_LOCATION=us-west1

echo "Date:    $(date)"
echo "Node:    $(hostname)"
echo "Job ID:  $SLURM_JOB_ID"
echo "Bench:   $BENCH"
echo "GPU:     $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo unknown)"
echo "----------------------------------------------------------------"

python scripts/batch_coordinator_jansen.py --bench "$BENCH"

echo "----------------------------------------------------------------"
echo "Done at $(date)"
