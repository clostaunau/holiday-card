#!/bin/bash
# check_types.sh - Run mypy type checking on Python files
#
# Usage:
#   ./scripts/check_types.sh              # Check all Python files in project
#   ./scripts/check_types.sh src/         # Check specific directory
#   ./scripts/check_types.sh file.py      # Check specific file
#   ./scripts/check_types.sh --strict     # Use strict mode

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
STRICT_MODE=false
TARGET="."
MYPY_OPTS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [TARGET]"
            echo ""
            echo "Options:"
            echo "  --strict    Use strict type checking mode"
            echo "  --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                # Check all files"
            echo "  $0 src/           # Check src directory"
            echo "  $0 file.py        # Check single file"
            echo "  $0 --strict src/  # Strict check on src"
            exit 0
            ;;
        *)
            TARGET=$1
            shift
            ;;
    esac
done

# Check if mypy is installed
if ! command -v mypy &> /dev/null; then
    echo -e "${RED}Error: mypy is not installed${NC}"
    echo "Install it with: pip install mypy"
    exit 1
fi

# Build mypy options
if [ "$STRICT_MODE" = true ]; then
    MYPY_OPTS="--strict"
fi

# Add common useful flags
MYPY_OPTS="$MYPY_OPTS --show-error-codes --pretty"

# Check for mypy config file
CONFIG_FILE=""
if [ -f "mypy.ini" ]; then
    CONFIG_FILE="mypy.ini"
    echo -e "${GREEN}Using config: mypy.ini${NC}"
elif [ -f "pyproject.toml" ] && grep -q "\[tool.mypy\]" pyproject.toml; then
    CONFIG_FILE="pyproject.toml"
    echo -e "${GREEN}Using config: pyproject.toml${NC}"
else
    echo -e "${YELLOW}Warning: No mypy config file found (mypy.ini or pyproject.toml)${NC}"
fi

# Run mypy
echo -e "${GREEN}Running mypy on: ${TARGET}${NC}"
echo "Command: mypy $MYPY_OPTS $TARGET"
echo ""

if mypy $MYPY_OPTS "$TARGET"; then
    echo ""
    echo -e "${GREEN}✓ Type checking passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Type checking failed${NC}"
    echo ""
    echo "Common fixes:"
    echo "  1. Add missing type hints to functions"
    echo "  2. Fix type mismatches (check error codes)"
    echo "  3. Add '# type: ignore[error-code]' for known false positives"
    echo "  4. Check mypy config for strictness settings"
    exit 1
fi
