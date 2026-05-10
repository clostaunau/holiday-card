#!/bin/bash
set -e

echo "=========================================="
echo "Setting up Holiday Card Creator Dev Container"
echo "=========================================="

# Add tools to PATH
export PATH="$HOME/.local/bin:$PATH"

# Install uv (fast Python package installer)
if ! command -v uv &> /dev/null; then
    echo "Installing uv (fast Python package installer)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "✓ uv already installed"
fi

# Install SpecKit via uv
if ! command -v specify &> /dev/null; then
    echo "Installing SpecKit..."
    uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
else
    echo "✓ SpecKit already installed"
fi

# Install Claude Code CLI
if ! command -v claude &> /dev/null; then
    echo "Installing Claude Code CLI..."
    curl -fsSL https://claude.ai/install.sh | bash || echo "⚠️  Claude CLI installation may need manual setup"
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "✓ Claude Code CLI already installed"
fi

echo ""
echo "=========================================="
echo "Installing holiday-card (editable, with dev tools)"
echo "=========================================="

# Single source of truth: pyproject.toml
pip install --upgrade pip
pip install -e ".[dev]"

# Install pre-commit hooks if config is present
if [ -f .pre-commit-config.yaml ] && command -v pre-commit &> /dev/null; then
    pre-commit install
    echo "✓ pre-commit hooks installed"
fi

echo ""
echo "=========================================="
echo "Installing BATS (Shell Script Testing)"
echo "=========================================="

if command -v bats &> /dev/null; then
    echo "✓ BATS (Bash Automated Testing System) is available"
else
    echo "Installing BATS for shell script testing..."
    git clone https://github.com/bats-core/bats-core.git /tmp/bats-core
    cd /tmp/bats-core
    ./install.sh /usr/local || echo "⚠️  BATS installation may require elevated privileges"
    cd -
    rm -rf /tmp/bats-core 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "Creating Project Structure"
echo "=========================================="

# Create runtime output directory if missing
mkdir -p output

echo ""
echo "=========================================="
echo "✓ Dev Container Setup Complete!"
echo "=========================================="
echo ""
echo "Installed Tools & Versions:"
echo "-------------------------------------------"
command -v python && python --version
command -v pip && pip --version
command -v uv && uv --version
command -v specify && echo "✓ SpecKit (specify)"
command -v claude && claude --version || echo "⚠️  Claude CLI (may need manual setup)"
command -v bats && bats --version
command -v holiday-card && holiday-card --version || echo "⚠️  holiday-card entry point not on PATH"

echo ""
echo "Quick Start:"
echo "-------------------------------------------"
echo "  holiday-card --help              # Show CLI usage"
echo "  holiday-card templates           # List available templates"
echo "  pytest                           # Run the test suite"
echo "  ruff check src/ tests/           # Lint"
echo "  mypy src/                        # Type-check"
echo ""
echo "Happy Holiday Card Creating! 🎄✨"
echo ""

exit 0
