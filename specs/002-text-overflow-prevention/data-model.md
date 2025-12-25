# Data Model: Text Overflow Prevention

**Feature**: 002-text-overflow-prevention
**Date**: 2025-12-25

## Overview

This document defines the data model enhancements for text overflow prevention. All changes are backward compatible - existing templates without overflow configuration will use default AUTO strategy.

---

## New Entities

### OverflowStrategy (Enum)

**Location**: `src/holiday_card/core/models.py`

**Definition**:
```python
class OverflowStrategy(str, Enum):
    """Strategy for handling text that exceeds designated boundaries.

    - AUTO: Automatically select best strategy based on text characteristics
    - SHRINK: Reduce font size until text fits (minimum 8pt)
    - WRAP: Break text into multiple lines
    - TRUNCATE: Cut off text with ellipsis (existing behavior)
    """

    AUTO = "auto"
    SHRINK = "shrink"
    WRAP = "wrap"
    TRUNCATE = "truncate"
```

**Values**:
- `AUTO` (default): Smart selection based on text length and context
- `SHRINK`: Reduce font size iteratively until fit
- `WRAP`: Multi-line text wrapping
- `TRUNCATE`: Ellipsis truncation (backward compatible with existing behavior)

**Usage in YAML**:
```yaml
text_elements:
  - content: "Merry Christmas!"
    overflow_strategy: "shrink"  # or "wrap", "truncate", "auto"
```

---

### AdjustmentResult (Model)

**Location**: `src/holiday_card/core/models.py`

**Definition**:
```python
class AdjustmentResult(BaseModel):
    """Result of text overflow adjustment.

    Used for debugging, logging, and future preview warnings.
    """

    was_adjusted: bool = Field(
        description="Whether any adjustment was applied"
    )
    strategy_applied: OverflowStrategy = Field(
        description="Strategy that was used"
    )
    original_font_size: int = Field(
        ge=6, le=144,
        description="Original font size in points"
    )
    final_font_size: int = Field(
        ge=6, le=144,
        description="Final font size after adjustment"
    )
    lines_used: int = Field(
        ge=1,
        description="Number of lines in final rendering"
    )
    content_truncated: bool = Field(
        default=False,
        description="Whether content was truncated"
    )
```

**Purpose**:
- Track what adjustments were made during rendering
- Enable future preview warnings (P3)
- Support debugging of overflow issues
- Provide telemetry for optimization

**Example**:
```python
result = AdjustmentResult(
    was_adjusted=True,
    strategy_applied=OverflowStrategy.SHRINK,
    original_font_size=36,
    final_font_size=24,
    lines_used=1,
    content_truncated=False
)
```

---

### TextMetrics (Model)

**Location**: `src/holiday_card/core/text_utils.py`

**Definition**:
```python
class TextMetrics(BaseModel):
    """Measured dimensions of rendered text.

    Used internally for overflow detection and fitting calculations.
    """

    width_pts: float = Field(
        ge=0.0,
        description="Calculated text width in points"
    )
    height_pts: float = Field(
        ge=0.0,
        description="Calculated text height in points"
    )
    line_count: int = Field(
        ge=1,
        description="Number of lines (1 for single-line)"
    )
    fits_within_bounds: bool = Field(
        description="Whether text fits in max_width and max_height"
    )
```

**Purpose**:
- Return structured measurement results
- Clearly indicate overflow conditions
- Support both width and height checking

**Example**:
```python
metrics = TextMetrics(
    width_pts=320.5,
    height_pts=36.0,
    line_count=1,
    fits_within_bounds=False  # Exceeds 300pt max width
)
```

---

## Modified Entities

### TextElement (Enhanced)

**Location**: `src/holiday_card/core/models.py`

**Current Definition** (from 001-holiday-card-generator):
```python
class TextElement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=1, max_length=1000)
    x: float = Field(ge=0.0)
    y: float = Field(ge=0.0)
    width: Optional[float] = Field(default=None, ge=0.0)
    font_family: str = Field(default="Helvetica")
    font_size: int = Field(default=12, ge=6, le=144)
    font_style: FontStyle = Field(default=FontStyle.NORMAL)
    color: Optional[Color] = Field(default=None)
    alignment: TextAlignment = Field(default=TextAlignment.LEFT)
    rotation: float = Field(default=0.0)
```

**Enhanced Definition** (with overflow prevention):
```python
class TextElement(BaseModel):
    # ... existing fields unchanged ...

    # NEW FIELDS for overflow prevention
    overflow_strategy: OverflowStrategy = Field(
        default=OverflowStrategy.AUTO,
        description="Strategy for handling text overflow"
    )
    max_lines: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum lines when using WRAP strategy (None = unlimited)"
    )
    min_font_size: int = Field(
        default=8,
        ge=6,
        le=72,
        description="Minimum font size for SHRINK strategy (points)"
    )

    # PRIVATE FIELD for adjustment tracking (not serialized to YAML)
    _adjustment_applied: Optional[AdjustmentResult] = PrivateAttr(default=None)

    def get_adjustment_result(self) -> Optional[AdjustmentResult]:
        """Get the overflow adjustment that was applied during rendering.

        Returns None if not yet rendered or no adjustment needed.
        """
        return self._adjustment_applied

    def set_adjustment_result(self, result: AdjustmentResult) -> None:
        """Internal use: Record adjustment result during rendering."""
        self._adjustment_applied = result
```

**Changes Summary**:
- Added `overflow_strategy` (default: AUTO)
- Added `max_lines` (for WRAP strategy, optional)
- Added `min_font_size` (for SHRINK strategy, default: 8pt)
- Added private `_adjustment_applied` (for debugging/preview)

**Backward Compatibility**:
- All new fields have sensible defaults
- Existing templates without these fields work unchanged
- Validation ensures valid enum values and constraints

---

## YAML Schema Updates

### Template YAML Schema

**Before** (existing):
```yaml
text_elements:
  - id: "greeting"
    content: "Merry Christmas!"
    x: 2.125
    y: 2.75
    font_family: "Helvetica"
    font_size: 36
    color:
      r: 1.0
      g: 1.0
      b: 1.0
```

**After** (with overflow prevention):
```yaml
text_elements:
  - id: "greeting"
    content: "Merry Christmas!"
    x: 2.125
    y: 2.75
    width: 4.0              # Max width (required for overflow detection)
    font_family: "Helvetica"
    font_size: 36
    color:
      r: 1.0
      g: 1.0
      b: 1.0
    overflow_strategy: "shrink"  # NEW: Optional (default: "auto")
    min_font_size: 10            # NEW: Optional (default: 8)
```

**Multi-line Message Example**:
```yaml
text_elements:
  - id: "message"
    content: "Wishing you joy and happiness this holiday season!"
    x: 0.5
    y: 3.0
    width: 3.25
    height: 2.0             # Height constraint for wrapping
    font_family: "Helvetica"
    font_size: 14
    overflow_strategy: "wrap"    # Wrap to multiple lines
    max_lines: 5                 # Limit to 5 lines
    alignment: "left"
```

---

## Entity Relationships

```
TextElement
├── has one → OverflowStrategy (enum value)
├── may have → max_lines (for WRAP)
├── may have → min_font_size (for SHRINK)
└── records → AdjustmentResult (after rendering)

AdjustmentResult
└── references → OverflowStrategy (which was applied)

TextMetrics
└── used internally (not persisted)
```

---

## Validation Rules

### TextElement Validation

1. **width must be specified for overflow detection**:
   - If `overflow_strategy` is not TRUNCATE and `width` is None, log warning
   - Overflow prevention requires known boundaries

2. **max_lines only relevant for WRAP**:
   - If `overflow_strategy` is WRAP and `max_lines` is None, unlimited wrapping
   - If `overflow_strategy` is not WRAP, `max_lines` is ignored

3. **min_font_size must be less than font_size**:
   - Pydantic validator ensures `min_font_size <= font_size`
   - Default 8pt minimum is sensible for most cases

4. **overflow_strategy must be valid enum value**:
   - Pydantic automatically validates against OverflowStrategy enum
   - Invalid values rejected at load time

---

## Migration Strategy

### Existing Templates

**No Changes Required**:
- Templates without `overflow_strategy` default to AUTO
- AUTO strategy provides smart behavior transparently
- Backward compatibility maintained

**Optional Enhancements**:
Template authors can explicitly configure overflow:
```yaml
# Front greeting - explicitly use shrink
text_elements:
  - content: "Happy Holidays!"
    overflow_strategy: "shrink"

# Inside message - explicitly use wrap
text_elements:
  - content: "Long message here..."
    overflow_strategy: "wrap"
    max_lines: 10
```

### Programmatic Usage

**Before**:
```python
text = TextElement(
    content="Merry Christmas!",
    x=2.0,
    y=3.0,
    font_size=36
)
```

**After** (with overflow control):
```python
text = TextElement(
    content="Merry Christmas!",
    x=2.0,
    y=3.0,
    width=4.0,  # Required for overflow detection
    font_size=36,
    overflow_strategy=OverflowStrategy.SHRINK,
    min_font_size=12  # Don't go below 12pt
)
```

---

## Database Schema

**N/A** - This project uses file-based storage (YAML). No database schema changes.

---

## API Compatibility

**All changes are backward compatible**:
- Optional fields with defaults
- Existing code works without modifications
- New functionality opt-in via YAML configuration

**Internal API additions** (for implementers):
```python
# In text_utils.py
def measure_text(...) -> TextMetrics
def shrink_to_fit(...) -> int
def wrap_text(...) -> list[str]

# In TextElement
def get_adjustment_result() -> Optional[AdjustmentResult]
```

**No breaking changes to public API**:
- `CardGenerator.create_card()` - unchanged
- `ReportLabRenderer.render_text()` - unchanged signature
- Template loading - backward compatible
