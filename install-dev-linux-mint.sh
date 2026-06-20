#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm dnsutils libxcb-cursor0 curl jq gawk
sudo npm install -g gamedig

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Done. Run with:"
echo "source .venv/bin/activate"
echo "python main.py"
