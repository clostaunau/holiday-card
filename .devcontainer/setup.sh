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
echo "Installing Python Development Tools"
echo "=========================================="

# Upgrade pip
pip install --upgrade pip

# Install Python development and testing tools
echo "Installing linters, formatters, and test tools..."
pip install --user black isort ruff pylint pytest pytest-cov mypy

echo ""
echo "=========================================="
echo "Installing Graphics & Document Libraries"
echo "=========================================="

# Install core graphics and PDF libraries for card creation
echo "Installing Pillow (image manipulation)..."
pip install --user Pillow

echo "Installing ReportLab (PDF generation)..."
pip install --user reportlab

echo "Installing svglib (SVG support)..."
pip install --user svglib

echo "Installing CairoSVG (advanced SVG rendering)..."
pip install --user cairosvg

echo "Installing PyPDF2 (PDF manipulation)..."
pip install --user pypdf2

# Install additional useful libraries for design
echo "Installing matplotlib (for charts/graphics)..."
pip install --user matplotlib

echo "Installing qrcode (for QR codes on cards)..."
pip install --user qrcode[pil]

# Install color and font utilities
echo "Installing colorama (colored terminal output)..."
pip install --user colorama

echo "Installing Pillow color utilities..."
pip install --user pillow-heif  # For HEIF/HEIC image support

echo ""
echo "=========================================="
echo "Installing Optional Web Preview Tools"
echo "=========================================="

# Install Flask for potential web-based card preview
echo "Installing Flask (web preview server)..."
pip install --user flask flask-cors

# Install Jinja2 for templating (useful for card templates)
echo "Installing Jinja2 (templating)..."
pip install --user jinja2

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

# Create basic project directories if they don't exist
mkdir -p output
mkdir -p templates
mkdir -p assets/images
mkdir -p assets/fonts
mkdir -p tests

echo "✓ Created project directories:"
echo "  - output/          (for generated cards)"
echo "  - templates/       (for card templates)"
echo "  - assets/images/   (for graphics and images)"
echo "  - assets/fonts/    (for custom fonts)"
echo "  - tests/           (for test files)"

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

echo ""
echo "Installed Python Libraries for Card Creation:"
echo "-------------------------------------------"
pip list | grep -E "(Pillow|reportlab|svglib|cairosvg|PyPDF2|matplotlib|qrcode|Flask|Jinja2)" || echo "Run 'pip list' to see all installed packages"

echo ""
echo "Quick Start Guide:"
echo "-------------------------------------------"
echo "1. Create card designs in Python using Pillow or ReportLab"
echo "2. Save generated cards to the 'output/' directory"
echo "3. Preview PDFs directly in VS Code"
echo "4. Run tests with: pytest tests/"
echo "5. Format code with: black ."
echo "6. Type check with: mypy ."
echo ""
echo "Example Commands:"
echo "  specify --help        # Get started with SpecKit"
echo "  claude --help         # Get started with Claude Code CLI"
echo "  python -m http.server # Start simple HTTP server (port 8000)"
echo "  flask run             # Run Flask preview server (port 5000)"
echo ""
echo "Happy Holiday Card Creating! 🎄✨"
echo ""

# Exit successfully
exit 0
