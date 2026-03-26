#!/usr/bin/env bash
# One-time setup: creates venv, installs dependencies, downloads history, and trains ML model.
set -e

PYTHON=${PYTHON:-python3}
VENV_DIR=".venv"

echo "==> Checking Python version..."
$PYTHON --version

echo "==> Creating virtual environment in $VENV_DIR..."
$PYTHON -m venv $VENV_DIR

echo "==> Activating venv and upgrading pip..."
source $VENV_DIR/bin/activate
pip install --upgrade pip --quiet

echo "==> Installing requirements (this may take a few minutes)..."
pip install -r requirements.txt

echo "==> Setting up .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  *** .env created from .env.example ***"
    echo "  Edit .env and fill in your MEXC API keys before continuing."
    echo ""
    read -p "  Press Enter once you have filled in .env to continue setup..."
else
    echo "  .env already exists — skipping."
fi

echo "==> Creating required data directories..."
mkdir -p data/raw data/processed data/db data/logs data/models

echo "==> Downloading historical OHLCV data (1 year)..."
python scripts/fetch_history.py

echo "==> Training ML model (XGBoost + RandomForest)..."
CSV_FILE=$(ls data/raw/*.csv 2>/dev/null | head -1)
if [ -z "$CSV_FILE" ]; then
    echo "ERROR: No CSV found in data/raw/ — fetch_history.py may have failed."
    exit 1
fi
echo "  Using: $CSV_FILE"
python scripts/train_model.py --csv "$CSV_FILE"

echo ""
echo "Setup complete. Run ./start.sh to launch the bot and dashboard."
