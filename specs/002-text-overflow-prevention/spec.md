# Feature Specification: Text Overflow Prevention

**Feature Branch**: `002-text-overflow-prevention`
**Created**: 2025-12-25
**Status**: Draft
**Input**: User description: "Ensure that any text used in the card fits within the boundaries designated for that text in the card layout. This is to prevent text from extending past the printed area."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Text Fitting via Font Size Reduction (Priority: P1)

A user creates a holiday card with a long greeting message on the front panel. The system automatically detects that the text would overflow its designated boundary and reduces the font size until the text fits completely within the allowed area.

**Why this priority**: This is the most critical capability because it directly solves the stated problem - preventing text from extending past printed boundaries. Font size reduction is the most common and intuitive solution that preserves all text content while maintaining readability.

**Independent Test**: Can be fully tested by creating a card with progressively longer text, verifying that the system reduces font size automatically and that all text remains visible within the designated boundary without manual intervention.

**Acceptance Scenarios**:

1. **Given** a text element with a long greeting that would overflow at the default font size, **When** the card is rendered, **Then** the font size is automatically reduced until all text fits within the designated width boundary
2. **Given** a text element that fits comfortably at its specified font size, **When** the card is rendered, **Then** the font size remains unchanged at the original size
3. **Given** a text element with extreme overflow that would require very small font size, **When** the card is rendered, **Then** the font size is reduced to a minimum readable threshold (e.g., 8pt) and then truncation is applied if still necessary
4. **Given** a text element with both width and height constraints, **When** the card is rendered, **Then** the font size is reduced to fit within both dimensions

---

### User Story 2 - Multi-Line Text Wrapping (Priority: P2)

A user adds a personalized inside message to a card that is several sentences long. The system automatically wraps the text across multiple lines to fit within the designated message area, maintaining proper spacing and alignment.

**Why this priority**: Text wrapping is essential for multi-paragraph content like inside messages where single-line display is not appropriate. This enhances the feature by providing a more natural layout for longer text, but requires the basic overflow detection from P1.

**Independent Test**: Can be tested by adding multi-sentence text to inside panels and verifying that text wraps to multiple lines with proper line spacing and that all lines fit within the vertical boundary of the text area.

**Acceptance Scenarios**:

1. **Given** a text element with multiple sentences that exceed the width boundary, **When** wrapping is enabled, **Then** the text wraps to multiple lines with proper word boundaries
2. **Given** wrapped text that fits within the vertical boundary, **When** the card is rendered, **Then** all lines are displayed with consistent line spacing
3. **Given** wrapped text that would overflow the vertical boundary, **When** the card is rendered, **Then** font size is reduced and wrapping is recalculated until all lines fit
4. **Given** a text element with explicit line breaks, **When** wrapping is enabled, **Then** explicit breaks are preserved in the final output

---

### User Story 3 - Configurable Overflow Strategy (Priority: P2)

A user wants control over how text overflow is handled for different parts of their card - using font reduction for the front greeting, wrapping for the inside message, and truncation with ellipsis for decorative text. The system allows specifying overflow strategies per text element.

**Why this priority**: Different text areas have different needs - a title looks better size-reduced, body text looks better wrapped, and decorative elements might prefer truncation. This provides user control but builds on P1/P2 infrastructure.

**Independent Test**: Can be tested by configuring different overflow strategies on different text elements and verifying each behaves according to its specified strategy.

**Acceptance Scenarios**:

1. **Given** a text element configured with "shrink" strategy, **When** overflow occurs, **Then** font size is reduced to fit
2. **Given** a text element configured with "wrap" strategy, **When** overflow occurs, **Then** text wraps to multiple lines
3. **Given** a text element configured with "truncate" strategy, **When** overflow occurs, **Then** text is truncated with ellipsis (existing behavior)
4. **Given** a text element with no explicit strategy, **When** overflow occurs, **Then** a sensible default strategy is applied based on the text element type (e.g., titles shrink, messages wrap)

---

### User Story 4 - Visual Overflow Warnings in Preview (Priority: P3)

A user previews their card design before printing and sees visual indicators showing which text areas were automatically adjusted for overflow. This allows them to decide whether to edit the text or accept the automatic adjustments.

**Why this priority**: This improves the user experience by making automatic adjustments transparent, but the core functionality works without it. Users can still verify output by examining the generated PDF.

**Independent Test**: Can be tested by creating a card with overflow scenarios and verifying that the preview mode displays visual indicators (highlighting, icons, or annotations) on text elements that were automatically adjusted.

**Acceptance Scenarios**:

1. **Given** a card with text that was auto-shrunk, **When** preview mode is enabled, **Then** the affected text element is highlighted with a visual indicator
2. **Given** a preview with overflow warnings, **When** the user clicks an indicator, **Then** details about the adjustment are displayed (original size, adjusted size, strategy used)
3. **Given** a card with no overflow issues, **When** preview mode is enabled, **Then** no warning indicators are shown

---

### User Story 5 - Boundary Enforcement Configuration (Priority: P3)

A power user wants to configure strict or relaxed boundary enforcement for their cards. Strict mode ensures text never exceeds boundaries (current requirement), while relaxed mode allows slight overflow into safe margins if it improves readability.

**Why this priority**: This provides advanced control for users who understand print workflows and may want to make trade-offs between strict compliance and aesthetic quality. It's optional and most users will use the default strict mode.

**Independent Test**: Can be tested by toggling between strict and relaxed modes and verifying that strict mode never allows overflow while relaxed mode permits controlled overflow within safe margins.

**Acceptance Scenarios**:

1. **Given** strict boundary enforcement is enabled, **When** any text would exceed its designated boundary, **Then** automatic adjustment is always applied
2. **Given** relaxed boundary enforcement is enabled, **When** text would slightly overflow but remains within safe margins, **Then** the text is rendered without adjustment
3. **Given** relaxed boundary enforcement is enabled, **When** text would exceed safe margins, **Then** automatic adjustment is applied as in strict mode

---

### Edge Cases

- What happens when a single word is too long to fit within the designated width even at minimum font size?
- How does the system handle text with very tall characters (e.g., uppercase with accents) that might exceed vertical boundaries?
- What happens when a text element has width but no height constraint specified?
- How does the system handle text overflow in rotated text elements?
- What happens when text wrapping is applied to a text element with center or right alignment?
- How does the system handle unicode characters, emojis, or special symbols that may render at different sizes?
- What happens when the minimum readable font size (e.g., 8pt) is larger than what's needed to fit the text?
- How does the system behave when multiple overflow strategies would conflict (e.g., shrink + wrap)?
- What happens when text elements are dynamically created with user input at runtime?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect when text content would exceed the designated width boundary of a text element
- **FR-002**: System MUST detect when text content would exceed the designated height boundary of a text element (if height is specified)
- **FR-003**: System MUST support automatic font size reduction as an overflow prevention strategy
- **FR-004**: System MUST reduce font size iteratively until text fits or a minimum threshold is reached
- **FR-005**: System MUST enforce a minimum readable font size of 8 points for auto-reduced text
- **FR-006**: System MUST support multi-line text wrapping as an overflow prevention strategy
- **FR-007**: System MUST wrap text at word boundaries (not mid-word) unless a word exceeds the width
- **FR-008**: System MUST apply truncation with ellipsis when text cannot fit even after reduction/wrapping
- **FR-009**: System MUST support configurable overflow strategies per text element (shrink, wrap, truncate)
- **FR-010**: System MUST apply default overflow strategy based on text element characteristics when no explicit strategy is specified
- **FR-011**: System MUST calculate text dimensions accurately before rendering using the selected font and size
- **FR-012**: System MUST respect the 0.25" safe margin requirement from all edges (from constitution principle IV)
- **FR-013**: System MUST handle text overflow for all text areas (front panel, back panel, inside panels)
- **FR-014**: System MUST work with all supported text alignments (left, center, right)
- **FR-015**: System MUST work with all supported font families and styles
- **FR-016**: System MUST preserve text color and other styling when applying overflow adjustments
- **FR-017**: System MUST work correctly with rotated text elements
- **FR-018**: System MUST provide a way to query whether a text element was adjusted for overflow (for preview warnings)
- **FR-019**: System MUST maintain print accuracy within 1mm tolerance when adjusting text (constitution principle IV)
- **FR-020**: Overflow detection and adjustment MUST occur before final PDF rendering

### Key Entities

- **TextElement**: Enhanced with overflow strategy configuration (shrink, wrap, truncate) and metadata about whether adjustment was applied
- **TextBoundary**: Represents the designated area for text (width and optional height) within which text must fit
- **OverflowStrategy**: Enumeration of approaches to handling text overflow (shrink, wrap, truncate, auto)
- **TextMetrics**: Calculated measurements of rendered text including actual width, height, and number of lines
- **AdjustmentResult**: Information about what adjustments were applied to fit text (original size, final size, lines used, strategy applied)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of generated cards have zero text overflow beyond designated boundaries (validated through automated tests)
- **SC-002**: Text remains readable at all sizes (minimum 8pt font size enforced)
- **SC-003**: Text overflow adjustment completes in under 100ms per text element (performance requirement)
- **SC-004**: Automated visual regression tests verify text fits correctly in all template types (half-fold, quarter-fold, tri-fold)
- **SC-005**: Manual testing confirms printed output has no text cutoff when folded (100% success rate across 10 test prints)
- **SC-006**: All existing card generation tests pass with overflow prevention enabled (backward compatibility)
- **SC-007**: Users can customize overflow strategy for at least 90% of common use cases without code changes

## Assumptions

- Text overflow is primarily a width-based problem; height overflow is less common but must be handled
- Most users will be satisfied with automatic overflow handling and won't need manual strategy configuration
- The existing TextElement model in `/workspaces/holiday-card/src/holiday_card/core/models.py` will be enhanced rather than replaced
- The existing ReportLab renderer in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py` will be the primary implementation target
- The existing `_handle_text_overflow` method (lines 295-326) will be replaced/enhanced as the foundation
- Preview renderer functionality will be added in a later phase if needed; initial focus is on PDF output correctness
- Template YAML files may need schema updates to support overflow strategy configuration
- Visual regression tests using pdf2image and imagehash (as specified in constitution principle VI) will validate text fitting
