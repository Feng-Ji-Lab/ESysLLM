#!/bin/bash
#SBATCH --job-name=vertex_smoke
#SBATCH --account=def-fji_gpu
#SBATCH --gpus-per-node=nvidia_h100_80gb_hbm3_1g.10gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=0:45:00
#SBATCH --output=%x-%j.out
#
# Single-PDF smoke test: run Dana2007.pdf through Marker with Vertex AI LLM,
# confirm we get JSON + table + figure crops.

set -e

module load python/3.11
source venv/bin/activate

echo "Date:    $(date)"
echo "Node:    $(hostname)"
echo "Job ID:  $SLURM_JOB_ID"
echo "GPU:     $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)"
echo "----------------------------------------------------------------"

cd format_conversion
# The Vertex workflow now reads marker_config_vertex.env directly, so no
# clobbering of the original marker_config.env (which holds GEMINI_API_KEY).

python run_workflow_v2_vertex.py \
    --pdf ../PDF/jansen_benchmark/vu2024/Dana2007.pdf \
    --device cuda --use-llm \
    -o ../mag_vertex_smoke_output

echo "----------------------------------------------------------------"
echo "=== Outputs ==="
ls -la ../mag_vertex_smoke_output/Dana2007/ || true
echo ""
echo "=== meta.json ==="
cat ../mag_vertex_smoke_output/Dana2007/Dana2007_meta.json 2>/dev/null || echo "missing"
echo ""
echo "=== Tables ==="
ls ../mag_vertex_smoke_output/Dana2007/tables/ 2>/dev/null | head -10 || true
echo "=== Figures ==="
ls ../mag_vertex_smoke_output/Dana2007/figures/ 2>/dev/null | head -10 || true

echo "Done at $(date)"
