#!/usr/bin/env bash
# ==============================================================================
#  ⚡ Hermes Kaggle Bridge 1-Liner Bootstrap
# ==============================================================================
set -e

echo "======================================================================"
echo "🚀 Initializing Hermes Kaggle 2xT4 Multi-GPU Server..."
echo "======================================================================"

# Install zstd if not present (required by Ollama extractor)
if ! command -v zstd &> /dev/null; then
    echo "📦 Installing zstd package..."
    apt-get update -qq && apt-get install -y -qq zstd
fi

# Run the python runner
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/server.py" "$@"
