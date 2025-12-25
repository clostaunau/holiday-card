# Technical Research: Text Overflow Prevention

**Feature**: 002-text-overflow-prevention
**Date**: 2025-12-25

## Research Questions

### Q1: How does ReportLab measure text dimensions?

**Investigation**: ReportLab's Canvas API provides `stringWidth(text, fontName, fontSize)` method.

**Findings**:
- `canvas.stringWidth(text, fontName, fontSize)` returns width in points
- Accurate for single-line text with specified font
- Does NOT account for line breaks or wrapping
- Font names must match ReportLab's registered fonts (e.g., "Helvetica", "Times-Roman")
- Returns float value (precise measurements)

**Decision**: Use `canvas.stringWidth()` for measuring single-line text width.

**Implications**:
- Need separate logic for multi-line text height calculation
- Must create temporary canvas for measurement if not rendering yet
- Font name mapping must be consistent between measurement and rendering

---

### Q2: What's the optimal algorithm for font size reduction?

**Options Evaluated**:

1. **Linear Search (decrement by 1pt)**
   - Pros: Simple, guaranteed to find solution
   - Cons: Slow for large reductions (36pt → 8pt = 28 iterations)

2. **Binary Search**
   - Pros: Fast (log₂N iterations), efficient for large ranges
   - Cons: Slightly more complex logic

3. **Percentage-based Reduction (10% steps)**
   - Pros: Fast for approximate fitting
   - Cons: May overshoot or undershoot optimal size

**Decision**: Implement binary search for font size reduction.

**Rationale**:
- Maximum 6 iterations for 6-144pt range (log₂(144-6) ≈ 7)
- Finds optimal size, not approximate
- Performance acceptable (<10ms per element)

**Algorithm**:
```python
def shrink_to_fit(content, font_name, initial_size, max_width, min_size=8):
    low, high = min_size, initial_size
    best_size = min_size

    while low <= high:
        mid = (low + high) // 2
        width = measure_width(content, font_name, mid)

        if width <= max_width:
            best_size = mid
            low = mid + 1  # Try larger size
        else:
            high = mid - 1  # Must shrink

    return best_size
```

---

### Q3: How should text wrapping be implemented?

**Options Evaluated**:

1. **Manual Word Wrapping**
   - Pros: Full control, no additional dependencies
   - Cons: Complex edge cases (hyphenation, unicode, whitespace)

2. **ReportLab Paragraph/Flowables**
   - Pros: Built-in, handles edge cases, supports styles
   - Cons: More complex API, requires Platypus framework

3. **Simple String Splitting**
   - Pros: Very simple
   - Cons: Doesn't handle word boundaries, poor quality

**Decision**: Use manual word wrapping with word boundary detection.

**Rationale**:
- ReportLab Paragraph requires Platypus (added complexity)
- Current rendering uses Canvas API directly (Paragraph is incompatible)
- Manual wrapping with `textwrap` module is straightforward
- Can measure each line with existing `stringWidth()` method

**Algorithm**:
```python
def wrap_text(content, font_name, font_size, max_width, max_lines=None):
    words = content.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        width = measure_width(test_line, font_name, font_size)

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Single word exceeds width - force break
                lines.append(word)

        if max_lines and len(lines) >= max_lines:
            break

    if current_line:
        lines.append(' '.join(current_line))

    return lines[:max_lines] if max_lines else lines
```

---

### Q4: What minimum font size ensures readability?

**Research**:
- **WCAG 2.1 AA**: Recommends minimum 12pt for body text (18pt for large text)
- **Print Industry Standard**: 8pt minimum for fine print
- **Mobile Accessibility**: 16pt+ recommended
- **Card Context**: Cards viewed at arm's length (~18-24 inches)

**Decision**: Minimum 8pt font size for overflow reduction.

**Rationale**:
- Cards are printed, not screens (different readability)
- 8pt is industry standard for fine print (greeting card legal text, etc.)
- Below 8pt becomes illegible for most readers
- If 8pt still overflows, truncation is more appropriate than unreadable text

**Fallback**: If text doesn't fit at 8pt, apply truncation with ellipsis.

---

### Q5: How should "auto" strategy select the appropriate approach?

**Heuristics Evaluated**:

| Context | Text Characteristics | Recommended Strategy |
|---------|---------------------|---------------------|
| Front panel greeting | Short (1-30 chars), single concept | SHRINK |
| Inside message | Long (50+ chars), multiple sentences | WRAP |
| Decorative label | Very short (<10 chars), single word | TRUNCATE |
| Back panel text | Medium (10-50 chars) | SHRINK if <30 chars, else WRAP |

**Decision**: Use rule-based heuristic for AUTO strategy.

**Algorithm**:
```python
def select_auto_strategy(text, panel_position, text_width, text_height):
    text_length = len(text)
    has_height_constraint = text_height is not None

    # Short text (titles, greetings) - shrink preserves all content
    if text_length < 30:
        return OverflowStrategy.SHRINK

    # Long text with height constraint - wrap is natural for paragraphs
    if text_length >= 30 and has_height_constraint:
        return OverflowStrategy.WRAP

    # Long text without height constraint - shrink to avoid multi-line
    if text_length >= 30 and not has_height_constraint:
        return OverflowStrategy.SHRINK

    # Default fallback
    return OverflowStrategy.SHRINK
```

---

### Q6: How to calculate line height for wrapped text?

**Research**:
- **Typography Standard**: 1.2x - 1.5x font size
- **Web Default**: 1.2x (CSS normal)
- **Print Default**: 1.2x - 1.3x
- **ReportLab Default**: 1.2x in Paragraph styles

**Decision**: Use 1.2x font size for line height.

**Calculation**:
```python
def calculate_line_height(font_size_pt):
    return font_size_pt * 1.2
```

**Example**: 12pt font → 14.4pt line height

---

### Q7: Performance profiling approach

**Baseline Measurement**:
- Current `_handle_text_overflow()` (truncation only): ~0.5ms per element
- Target: <100ms per element (200x margin)

**Profiling Plan**:
1. Measure `stringWidth()` call time (expect <0.1ms)
2. Measure binary search iterations (expect 5-7 iterations × 0.1ms = 0.5-0.7ms)
3. Measure wrapping algorithm (expect 1-2ms for typical text)
4. Total per-element budget: ~2-5ms (well under 100ms)

**Optimization Opportunities** (if needed):
- Cache font metrics for repeated measurements
- Pre-calculate common font/size combinations
- Limit binary search iterations (max 10)

**Decision**: No premature optimization - implement straightforward algorithms and profile in tests.

---

## Key Technical Decisions Summary

1. **Text Width Measurement**: ReportLab `canvas.stringWidth()`
2. **Font Size Reduction**: Binary search (6-144pt range)
3. **Text Wrapping**: Manual word boundary wrapping
4. **Minimum Font Size**: 8pt (print industry standard)
5. **Auto Strategy**: Rule-based heuristic (length + context)
6. **Line Height**: 1.2x font size
7. **Performance**: Profile in tests, optimize only if needed

---

## Dependencies

**No New Dependencies**:
- All functionality uses existing ReportLab APIs
- Python standard library for string operations
- Pydantic for model validation (already present)

---

## Open Questions

**Q**: Should we support right-to-left (RTL) languages?
- **Answer**: Out of scope for P1. Existing rendering doesn't handle RTL, so overflow prevention inherits the limitation.

**Q**: Should we cache measurement results?
- **Answer**: Profile first. Caching adds complexity and may not be needed for typical 5-10 elements per card.

**Q**: How to handle emoji/unicode width?
- **Answer**: ReportLab's `stringWidth()` handles unicode. If inaccurate, add 5% safety margin.

---

## References

- ReportLab User Guide: Chapter 4 (Canvas API)
- WCAG 2.1: Success Criterion 1.4.4 (Resize Text)
- Typography Best Practices: "The Elements of Typographic Style" (Bringhurst)
- Python textwrap module documentation
