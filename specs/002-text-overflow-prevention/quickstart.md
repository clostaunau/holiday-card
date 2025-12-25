# Quickstart Guide: Text Overflow Prevention

**Feature**: 002-text-overflow-prevention
**Audience**: Template authors, developers using the holiday-card library

## Overview

Text overflow prevention ensures that all text in your holiday cards fits within designated boundaries. The system automatically detects overflow and applies one of three strategies: shrink (reduce font size), wrap (multi-line), or truncate (ellipsis).

---

## Quick Start (5 minutes)

### 1. Basic Usage - Automatic Overflow Handling

**The simplest approach**: Just specify a `width` for your text elements.

```yaml
# templates/my-card/card.yaml
text_elements:
  - content: "Merry Christmas and Happy New Year!"
    x: 2.0
    y: 3.0
    width: 4.0        # Text must fit within 4 inches
    font_size: 36
```

**What happens**:
- System detects "Merry Christmas and Happy New Year!" is too long at 36pt
- AUTO strategy selects SHRINK (short greeting text)
- Font size reduced to ~24pt to fit within 4.0" width
- Minimum 8pt enforced (if text still too long, truncates with "...")

**No code changes needed** - this works with existing `CardGenerator.create_and_generate()`.

---

### 2. Explicit Strategy - Control the Behavior

**Choose how overflow is handled** for each text element.

#### Example: Shrink Strategy (for titles/greetings)

```yaml
text_elements:
  - id: "front-greeting"
    content: "Season's Greetings!"
    x: 2.0
    y: 3.0
    width: 4.0
    font_size: 48
    overflow_strategy: "shrink"    # Reduce font size to fit
    min_font_size: 12              # Don't go below 12pt
```

#### Example: Wrap Strategy (for messages)

```yaml
text_elements:
  - id: "inside-message"
    content: "Wishing you and your family joy, peace, and happiness this holiday season and throughout the coming year!"
    x: 0.5
    y: 3.0
    width: 3.5
    height: 2.5                    # Height constraint
    font_size: 14
    overflow_strategy: "wrap"      # Multi-line wrapping
    max_lines: 5                   # Limit to 5 lines
    alignment: "left"
```

#### Example: Truncate Strategy (for labels)

```yaml
text_elements:
  - id: "from-label"
    content: "From: The Smithsonian Family"
    x: 1.0
    y: 0.5
    width: 2.0
    font_size: 10
    overflow_strategy: "truncate"  # Cut with ellipsis if too long
```

---

### 3. Programmatic Usage

```python
from holiday_card.core.models import TextElement, OverflowStrategy
from holiday_card.core.generators import CardGenerator

# Create text with overflow prevention
greeting = TextElement(
    content="Merry Christmas and Happy New Year to Everyone!",
    x=2.0,
    y=3.0,
    width=4.0,
    font_size=36,
    overflow_strategy=OverflowStrategy.SHRINK,
    min_font_size=12
)

# Use normally with CardGenerator
generator = CardGenerator()
card, pdf_path = generator.create_and_generate(
    template_id="christmas-classic",
    output_path=Path("output/my-card.pdf"),
    message="Merry Christmas and Happy New Year to Everyone!"
)

# Check if text was adjusted (for debugging)
for panel in card.panels:
    for text in panel.text_elements:
        result = text.get_adjustment_result()
        if result and result.was_adjusted:
            print(f"Text adjusted: {result.original_font_size}pt → {result.final_font_size}pt")
```

---

## Strategy Selection Guide

### When to Use SHRINK

**Best for**:
- Short greetings (1-5 words)
- Titles and headings
- Front panel text
- Text where all content must be visible

**Example**:
```yaml
overflow_strategy: "shrink"
content: "Happy Holidays!"
```

**Behavior**:
- Reduces font size iteratively until text fits
- Minimum 8pt (configurable with `min_font_size`)
- If minimum reached and still too long, truncates with "..."

---

### When to Use WRAP

**Best for**:
- Long messages (sentences/paragraphs)
- Inside panel text
- Text with natural line breaks
- Text where multi-line is acceptable

**Example**:
```yaml
overflow_strategy: "wrap"
content: "Wishing you joy and happiness this holiday season!"
max_lines: 3  # Optional limit
```

**Behavior**:
- Wraps at word boundaries
- Respects `max_lines` if specified
- If wrapped text exceeds `height`, reduces font size
- Line height = 1.2x font size

---

### When to Use TRUNCATE

**Best for**:
- Labels and metadata
- Text where partial content is acceptable
- Decorative text
- Legacy compatibility

**Example**:
```yaml
overflow_strategy: "truncate"
content: "From: John Smith"
```

**Behavior**:
- Cuts text at width boundary
- Adds "..." ellipsis
- No font size reduction
- Single line only

---

### When to Use AUTO

**Best for**:
- Most cases (smart selection)
- When you're unsure
- Default behavior

**Example**:
```yaml
overflow_strategy: "auto"  # or omit (this is default)
content: "Any text here"
```

**Behavior**:
- Text length < 30 chars: SHRINK
- Text length ≥ 30 chars with height: WRAP
- Text length ≥ 30 chars without height: SHRINK
- Smart defaults based on context

---

## Testing Your Templates

### Validate Overflow Handling

Create test cards with varying text lengths:

```python
from pathlib import Path
from holiday_card.core.generators import CardGenerator

generator = CardGenerator()

# Test cases
test_messages = [
    "Short",
    "Medium length greeting",
    "Very long greeting message that will definitely overflow the designated area!",
    "Extremely long message with multiple sentences that should wrap to many lines. This tests the wrapping behavior."
]

for i, msg in enumerate(test_messages):
    card, pdf = generator.create_and_generate(
        template_id="christmas-classic",
        output_path=Path(f"output/test_{i}.pdf"),
        message=msg
    )
    print(f"Generated: test_{i}.pdf with message length {len(msg)}")
```

### Visual Inspection

1. Generate test PDFs
2. Print on standard 8.5" x 11" paper
3. Fold according to fold type
4. Verify:
   - Text fits within panel boundaries
   - Text is readable (not too small)
   - Wrapping looks natural (if used)
   - No text cutoff

---

## Common Scenarios

### Scenario 1: Front Greeting Too Long

**Problem**: "Merry Christmas and Happy New Year!" at 48pt exceeds 4" width

**Solution**:
```yaml
text_elements:
  - content: "Merry Christmas and Happy New Year!"
    width: 4.0
    font_size: 48
    overflow_strategy: "shrink"
    min_font_size: 24  # Don't go below 24pt for front greeting
```

**Result**: Font size reduced to ~32pt to fit within 4.0"

---

### Scenario 2: Inside Message Needs Wrapping

**Problem**: Long personalized message doesn't fit on single line

**Solution**:
```yaml
text_elements:
  - content: "Dear John and Mary, Wishing you both a wonderful holiday season filled with joy, laughter, and cherished moments with family and friends!"
    width: 3.5
    height: 3.0
    font_size: 12
    overflow_strategy: "wrap"
    max_lines: 6
    alignment: "left"
```

**Result**: Text wraps to 4-5 lines, all within 3.5" × 3.0" area

---

### Scenario 3: Dynamic User Input

**Problem**: User provides arbitrary-length greeting via CLI

**Solution**: Use AUTO strategy (default) - it adapts to text length

```python
# In CLI code
user_message = input("Enter your greeting: ")  # Could be any length

card, pdf = generator.create_and_generate(
    template_id="christmas-classic",
    output_path=output_path,
    message=user_message  # AUTO handles short or long
)
```

**Result**: Short messages stay large, long messages shrink or wrap automatically

---

### Scenario 4: Multi-Language Support

**Problem**: German/Spanish messages often longer than English equivalents

**Solution**: Set generous widths and use AUTO or WRAP

```yaml
text_elements:
  - content: "Frohe Weihnachten und ein glückliches neues Jahr!"
    width: 4.5  # Extra width for longer languages
    font_size: 36
    overflow_strategy: "auto"
```

---

## Troubleshooting

### Text Too Small After Shrinking

**Symptom**: Font size reduced to 8pt, barely readable

**Diagnosis**: Text too long for designated width

**Solutions**:
1. Increase `width` in template
2. Reduce `font_size` starting point
3. Use WRAP instead of SHRINK
4. Shorten content

```yaml
# Before (too small)
width: 3.0
font_size: 48
overflow_strategy: "shrink"

# After (better)
width: 4.5        # Increased width
font_size: 36     # Lower starting point
overflow_strategy: "wrap"  # Or switch to wrapping
```

---

### Wrapped Text Exceeds Panel Height

**Symptom**: Text wraps but bottom lines cut off

**Diagnosis**: Wrapped lines exceed `height` constraint

**Solutions**:
1. Increase `height` in template
2. Set `max_lines` to limit wrapping
3. Reduce `font_size`
4. System will auto-reduce font if wrapping doesn't fit

```yaml
# System auto-adjusts
width: 3.0
height: 2.0
font_size: 14
overflow_strategy: "wrap"
# If 14pt wrapping exceeds 2.0", font size auto-reduced to 12pt
```

---

### Text Still Overflows

**Symptom**: Text exceeds boundaries even with overflow prevention

**Diagnosis**:
- Width not specified (overflow detection disabled)
- Minimum font size too large
- Extreme edge case

**Solutions**:
1. Ensure `width` is specified
2. Lower `min_font_size` (default 8pt)
3. Check for special characters/emojis affecting width

```yaml
# Ensure width specified
text_elements:
  - content: "Text"
    x: 1.0
    y: 1.0
    width: 3.0  # REQUIRED for overflow detection
```

---

### Strategy Selection Wrong

**Symptom**: AUTO picks WRAP but you wanted SHRINK

**Diagnosis**: AUTO heuristic doesn't match your preference

**Solution**: Explicitly specify strategy

```yaml
# Override AUTO
overflow_strategy: "shrink"  # or "wrap" or "truncate"
```

---

## Advanced Configuration

### Custom Minimum Font Size

```yaml
text_elements:
  - content: "Important Notice"
    font_size: 24
    min_font_size: 14  # Don't go below 14pt (default is 8pt)
    overflow_strategy: "shrink"
```

### Unlimited Line Wrapping

```yaml
text_elements:
  - content: "Very long message..."
    overflow_strategy: "wrap"
    max_lines: null  # or omit - unlimited wrapping
```

### Combining Width and Height Constraints

```yaml
text_elements:
  - content: "Message"
    width: 3.5   # Horizontal boundary
    height: 2.5  # Vertical boundary
    overflow_strategy: "wrap"
    # System ensures wrapped text fits within BOTH constraints
```

---

## Performance Considerations

- **Measurement overhead**: ~1-5ms per text element
- **Shrink algorithm**: 5-7 iterations (binary search)
- **Wrap algorithm**: ~1-2ms for typical messages
- **Total impact**: ~5-25ms per card (5 text elements)

**No noticeable performance impact** for typical use cases.

---

## Next Steps

1. **Update your templates**: Add `width` and `overflow_strategy` to text elements
2. **Test with long text**: Verify overflow handling works as expected
3. **Print and fold**: Confirm text fits on physical cards
4. **Iterate**: Adjust widths, strategies, and font sizes as needed

For implementation details, see:
- [plan.md](./plan.md) - Technical architecture
- [data-model.md](./data-model.md) - Data structures
- [research.md](./research.md) - Technical decisions
