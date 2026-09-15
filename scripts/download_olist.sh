#!/usr/bin/env bash
# Downloads the Olist dataset into data/raw with the Kaggle CLI.
# Needs a Kaggle API token in ~/.kaggle/kaggle.json.
# No Kaggle CLI? Download the zip from
# https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and unzip into data/raw.
set -euo pipefail
cd "$(dirname "$0")/.."

pip install --quiet kaggle
mkdir -p data/raw
kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip

ls -lh data/raw/*.csv
n=$(ls data/raw/*.csv | wc -l | tr -d ' ')
if [ "$n" -eq 9 ]; then echo "OK: 9 CSV files"; else echo "WARNING: expected 9 CSV files, found $n"; fi
