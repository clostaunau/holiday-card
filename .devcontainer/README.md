# Holiday Card Creator - Development Container

This devcontainer is optimized for Python development of a holiday card creation utility with graphics manipulation, PDF generation, and printable card design capabilities.

## What's Included

### Base Image
- **Python 3.12** (latest stable version)
- Debian-based container with common utilities
- Non-root user (vscode) for security

### Graphics & Document Generation Libraries

**Core Libraries:**
- **Pillow (PIL)**: Comprehensive image manipulation and graphics creation
- **ReportLab**: Professional PDF generation with precise layout control
- **svglib**: SVG file support and conversion
- **CairoSVG**: Advanced SVG rendering capabilities
- **PyPDF2**: PDF file manipulation and merging

**Design Utilities:**
- **matplotlib**: Charts, graphs, and data visualization
- **qrcode**: QR code generation for cards
- **pillow-heif**: HEIF/HEIC image format support
- **colorama**: Colored terminal output

**Web Preview:**
- **Flask**: Lightweight web server for card preview
- **Flask-CORS**: Cross-origin support
- **Jinja2**: Template engine for card layouts

### Python Development Tools

**Installed via setup.sh:**
- **uv**: Ultra-fast Python package installer
- **black**: Code formatter (PEP 8 compliant)
- **isort**: Import statement organizer
- **ruff**: Fast Python linter
- **pylint**: Comprehensive Python linter
- **pytest**: Modern testing framework
- **pytest-cov**: Test coverage reporting
- **mypy**: Static type checker

**Additional Tools:**
- **SpecKit**: Specification and documentation framework
- **Claude Code CLI**: AI-powered development assistant
- **BATS**: Bash Automated Testing System
- **Git** and **GitHub CLI**: Version control and GitHub operations

### VS Code Extensions

**Python Development:**
- Python language support (ms-python.python)
- Pylance for advanced IntelliSense
- Black formatter integration
- isort for import organization
- Ruff linter
- Python debugger (debugpy)

**Graphics & Design:**
- PDF viewer and preview (tomoki1207.pdf)
- Color picker for design work (anseki.vscode-color)
- Jupyter notebook support (for iterative design)

**Productivity:**
- GitLens for enhanced Git features
- TOML and YAML file support
- Markdown preview and editing
- GitHub Copilot (optional, if you have access)

### Project Structure

The setup script automatically creates these directories:

```
holiday-card/
├── .devcontainer/          # Dev container configuration
├── output/                 # Generated holiday cards (PDFs, images)
├── templates/              # Card design templates
├── assets/
│   ├── images/            # Graphics, logos, decorations
│   └── fonts/             # Custom fonts for cards
├── tests/                 # Test files
└── src/                   # Source code (create as needed)
```

### Features

**Development Environment:**
- Auto-formatting on save (Black)
- Import organization on save (isort)
- Type hints and inlay hints enabled
- Color decorators for better visibility
- SSH key mounting from host machine

**Port Forwarding:**
- Port 8000: Card Preview Server
- Port 8080: HTTP Server
- Port 5000: Flask Development Server

**Environment Variables:**
- `PYTHONUNBUFFERED=1`: Real-time output
- `PYTHONDONTWRITEBYTECODE=1`: No .pyc files

## Usage

### Getting Started

1. **Open in Dev Container**
   - Open this repository in VS Code
   - When prompted, click "Reopen in Container"
   - Or use Command Palette: `Dev Containers: Reopen in Container`

2. **Wait for Setup**
   - First build takes 5-10 minutes
   - Installs all dependencies automatically
   - Subsequent builds are much faster (cached)

3. **Verify Installation**
   ```bash
   python --version          # Should show Python 3.12.x
   pip list | grep Pillow    # Verify Pillow is installed
   pip list | grep reportlab # Verify ReportLab is installed
   ```

### Creating Holiday Cards

#### Using Pillow (Image-based Cards)

```python
from PIL import Image, ImageDraw, ImageFont

# Create a blank card (8.5" x 5.5" at 300 DPI = 2550 x 1650 pixels)
width, height = 2550, 1650
card = Image.new('RGB', (width, height), color='white')
draw = ImageDraw.Draw(card)

# Add text, graphics, etc.
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
draw.text((width//2, height//2), "Happy Holidays!", fill='red', font=font, anchor='mm')

# Save the card
card.save('output/holiday_card.png')
```

#### Using ReportLab (PDF Cards)

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

# Create PDF card
c = canvas.Canvas("output/holiday_card.pdf", pagesize=letter)
width, height = letter

# Add content
c.setFont("Helvetica-Bold", 36)
c.drawCentredString(width/2, height/2, "Season's Greetings!")

c.save()
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_card_generator.py
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
ruff check .

# Type checking
mypy src/
```

### Web Preview Server

```bash
# Simple HTTP server (view generated cards)
python -m http.server 8000

# Flask development server (if you create a Flask app)
flask run --host=0.0.0.0 --port=5000
```

Then open the forwarded port in your browser to preview cards.

## Customization

### Adding Project Dependencies

Create a `requirements.txt` file in your project root:

```txt
# requirements.txt
Pillow>=10.0.0
reportlab>=4.0.0
svglib>=1.5.0
cairosvg>=2.7.0
PyPDF2>=3.0.0
```

Update `postCreateCommand` in `devcontainer.json`:
```json
"postCreateCommand": "bash .devcontainer/setup.sh && pip install -r requirements.txt"
```

### Using pyproject.toml

For modern Python projects, create `pyproject.toml`:

```toml
[project]
name = "holiday-card-creator"
version = "0.1.0"
description = "Create beautiful printable holiday cards"
requires-python = ">=3.12"
dependencies = [
    "Pillow>=10.0.0",
    "reportlab>=4.0.0",
    "svglib>=1.5.0",
]

[project.optional-dependencies]
dev = [
    "black>=23.0.0",
    "pytest>=7.0.0",
    "mypy>=1.0.0",
]
```

Install with:
```bash
pip install -e ".[dev]"
```

### Adding Custom Fonts

1. Download TrueType (.ttf) or OpenType (.otf) fonts
2. Place them in `assets/fonts/`
3. Use in code:

```python
from PIL import ImageFont

font = ImageFont.truetype("assets/fonts/YourFont.ttf", 48)
```

### Image Assets

- Place holiday graphics, logos, borders in `assets/images/`
- Supported formats: PNG, JPEG, SVG, HEIF/HEIC
- Use with Pillow:

```python
from PIL import Image

decoration = Image.open('assets/images/snowflake.png')
card.paste(decoration, (100, 100))
```

## Card Design Tips

### Standard Card Sizes (at 300 DPI)

| Card Size | Dimensions (inches) | Pixels (300 DPI) |
|-----------|-------------------|------------------|
| Standard | 5" x 7" | 1500 x 2100 |
| A2 | 4.25" x 5.5" | 1275 x 1650 |
| Folded Letter | 8.5" x 5.5" | 2550 x 1650 |
| Square | 5" x 5" | 1500 x 1500 |

### Print-Ready Settings

- **Resolution**: 300 DPI minimum
- **Color Mode**: RGB for screen, CMYK for professional printing
- **Format**: PDF for best print quality
- **Bleed**: Add 0.125" margin for professional printing

### Example: Folded Card Template

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

# Create 8.5" x 11" sheet that folds to 8.5" x 5.5"
c = canvas.Canvas("output/folded_card.pdf", pagesize=letter)
width, height = letter

# Front of card (bottom half when folded)
c.drawCentredString(width/2, height/4, "Happy Holidays!")

# Inside of card (top half when folded)
c.drawCentredString(width/2, 3*height/4, "Wishing you joy and peace!")

c.save()
```

## Troubleshooting

### Font Issues

If fonts don't render correctly:
```bash
# List available fonts
fc-list

# Install additional fonts (in devcontainer)
sudo apt-get update && sudo apt-get install -y fonts-liberation fonts-dejavu-extra
```

### Image Quality Issues

- Use 300 DPI for print-quality output
- Save as PNG for lossless images
- Use PDF for vector graphics and text

### Container Rebuild

If dependencies aren't working:
```bash
# In VS Code Command Palette
> Dev Containers: Rebuild Container
```

## Resources

### Library Documentation
- [Pillow Documentation](https://pillow.readthedocs.io/)
- [ReportLab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [svglib Documentation](https://github.com/deeplook/svglib)
- [CairoSVG Documentation](https://cairosvg.org/)

### Design Resources
- [Google Fonts](https://fonts.google.com/) - Free fonts
- [Unsplash](https://unsplash.com/) - Free high-quality images
- [Canva](https://www.canva.com/) - Design inspiration

### Python Resources
- [Python Imaging Library Handbook](https://pillow.readthedocs.io/en/stable/handbook/)
- [ReportLab Graphics](https://www.reportlab.com/docs/reportlab-graphics.pdf)

## SSH Keys

Your local SSH keys are mounted read-only into the container at `/home/vscode/.ssh`, allowing you to:
- Push/pull from Git repositories
- Access remote servers
- Use SSH-based authentication

## Support

For issues specific to:
- **Devcontainer setup**: Check VS Code Dev Containers documentation
- **Python libraries**: Refer to library-specific documentation
- **SpecKit**: Run `specify --help`
- **Claude CLI**: Run `claude --help`

---

**Ready to create beautiful holiday cards!** Start by exploring the examples above or use the installed tools to build your card creation workflow.
