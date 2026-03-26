#!/usr/bin/env bash
# One-time setup: creates venv, installs dependencies, and prepares .env
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
    echo "  Edit .env and fill in your MEXC API keys before running the bot."
    echo ""
else
    echo "  .env already exists — skipping."
fi

echo "==> Creating required data directories..."
mkdir -p data/raw data/processed data/db data/logs data/models

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Edit .env with your MEXC API credentials"
echo "  2. (Optional) Download history and train ML model:"
echo "       source .venv/bin/activate"
echo "       python scripts/fetch_history.py"
echo "       python scripts/train_model.py"
echo "  3. Start the bot:"
echo "       ./start.sh"
