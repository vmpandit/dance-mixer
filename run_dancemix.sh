#!/bin/zsh
# -----------------------------------------------------------------------------
# Dance Mix Builder launcher
#
# Author: Vivek Pandit
# Initial implementation support: Perplexity, powered by GPT-5.4 Thinking
#
# Purpose:
# - Move into the project directory
# - Activate the local Python virtual environment
# - Run the Dance Mix Builder script
#
# Notes:
# - This launcher assumes the project lives in:
#     /Users/vivekpandit/Downloads/dancemix
# - If you move the project later, update PROJECT_DIR below.
# - The Python script itself contains the main legal / usage notes.
# -----------------------------------------------------------------------------

set -e

PROJECT_DIR="/Users/vivekpandit/Downloads/dancemix"
VENV_DIR="$PROJECT_DIR/.venv"
SCRIPT_PATH="$PROJECT_DIR/youtube_dance_mix.py"

cd "$PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Error: virtual environment not found at $VENV_DIR"
  echo "Create it first, then install the required Python packages."
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Error: Python script not found at $SCRIPT_PATH"
  exit 1
fi

source "$VENV_DIR/bin/activate"
python "$SCRIPT_PATH"
