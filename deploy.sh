#!/usr/bin/env bash
set -e

# --- Variables ---
PROJECT_DIR="$(pwd)"
SRC_DIR="$PROJECT_DIR/src/discord_bot"
VENDOR_DIR="$SRC_DIR/vendor"
REQ_FILE="$PROJECT_DIR/src/discord_bot/requirements.txt"

# --- Step 1: Clean old vendor folder ---
echo "Cleaning old vendor folder..."
rm -rf "$VENDOR_DIR"
mkdir -p "$VENDOR_DIR"

# --- Step 2: Install dependencies into vendor/ ---
echo "Installing dependencies into vendor/..."
python3.12 -m pip install --upgrade pip
python3.12 -m pip install -r "$REQ_FILE" -t "$VENDOR_DIR"

# --- Step 3: Optional: list installed packages ---
echo "Installed packages:"
ls -1 "$VENDOR_DIR" | sort

# --- Step 4: SAM build & deploy ---
echo "Building SAM project..."
sam build

echo "Deploying SAM project..."
sam deploy --guided

echo "Done! Vendor folder is Lambda-compatible."
