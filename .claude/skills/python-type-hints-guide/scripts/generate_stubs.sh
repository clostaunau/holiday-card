#!/bin/bash
# generate_stubs.sh - Generate type stub files for Python code
#
# Usage:
#   ./scripts/generate_stubs.sh module_name       # Generate stubs for module
#   ./scripts/generate_stubs.sh -p package_name   # Generate stubs for package
#   ./scripts/generate_stubs.sh -o output_dir     # Specify output directory

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
OUTPUT_DIR="stubs"
PACKAGE_MODE=false
TARGET=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--package)
            PACKAGE_MODE=true
            TARGET=$2
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR=$2
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [MODULE]"
            echo ""
            echo "Options:"
            echo "  -p, --package PKG  Generate stubs for package"
            echo "  -o, --output DIR   Output directory (default: stubs)"
            echo "  --help             Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 mymodule              # Generate stubs for mymodule.py"
            echo "  $0 -p mypackage          # Generate stubs for package"
            echo "  $0 -o typings mymodule   # Custom output directory"
            exit 0
            ;;
        *)
            TARGET=$1
            shift
            ;;
    esac
done

# Check if target is provided
if [ -z "$TARGET" ]; then
    echo -e "${RED}Error: No module or package specified${NC}"
    echo "Use --help for usage information"
    exit 1
fi

# Check if stubgen is installed (comes with mypy)
if ! command -v stubgen &> /dev/null; then
    echo -e "${RED}Error: stubgen is not installed${NC}"
    echo "Install it with: pip install mypy"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Generate stubs
echo -e "${GREEN}Generating type stubs...${NC}"

if [ "$PACKAGE_MODE" = true ]; then
    echo "Package: $TARGET"
    echo "Output: $OUTPUT_DIR"
    echo ""
    stubgen -p "$TARGET" -o "$OUTPUT_DIR"
else
    echo "Module: $TARGET"
    echo "Output: $OUTPUT_DIR"
    echo ""
    stubgen -m "$TARGET" -o "$OUTPUT_DIR"
fi

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Stub files generated successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review generated .pyi files in $OUTPUT_DIR"
    echo "  2. Add more specific type hints as needed"
    echo "  3. Add to your project's type stub path"
    echo ""
    echo "Note: Generated stubs are a starting point."
    echo "You should review and enhance them for accuracy."
else
    echo ""
    echo -e "${RED}✗ Stub generation failed${NC}"
    exit 1
fi
