# Backend conformance matrix

<!-- Generated from tests/conformance/capabilities.py; do not edit by hand. -->
<!-- Regenerate: python -m tests.conformance.capabilities > docs/conformance-matrix.md -->

Each case in `tests/conformance/cases.py` is rendered by every backend and
compared against the SVG backend (the oracle, D12) at 144 DPI.

- `match`: within tolerance of the SVG raster.
- `raises`: the backend raises `NotImplementedError` (D4).
- `known_diff (#N)`: differs from SVG; issue #N owns the fix.

| case | pdf | png |
|---|---|---|
| `rect_fill` | match | match |
| `rect_rounded` | match | match |
| `circle_fill` | match | match |
| `ellipse_fill` | match | match |
| `polygon_star` | match | match |
| `polyline_stroke` | match | match |
| `path_cubic` | match | match |
| `path_quadratic` | match | match |
| `stroke_rect_6pt` | match | known_diff (#77) |
| `stroke_dash_line_2` | match | match |
| `stroke_dash_line_1` | match | match |
| `stroke_dash_line_4` | match | match |
| `linear_gradient` | match | match |
| `radial_gradient` | match | match |
| `pattern_stripes_0` | match | match |
| `pattern_stripes_45` | match | match |
| `pattern_stripes_90` | match | match |
| `pattern_dots_0` | match | match |
| `pattern_dots_45` | match | match |
| `pattern_dots_90` | match | match |
| `pattern_grid_0` | match | match |
| `pattern_grid_45` | match | match |
| `pattern_grid_90` | match | match |
| `pattern_checkerboard_0` | match | match |
| `pattern_checkerboard_45` | match | match |
| `pattern_checkerboard_90` | match | match |
| `clip_circle_over_rect` | match | match |
| `clip_nested` | match | match |
| `group_rotate_pivot` | match | match |
| `group_scale_pivot` | match | match |
| `group_square_scale2_pivot` | match | match |
| `group_square_scale2_rotate30` | match | match |
| `group_square_scale2_offset` | match | match |
| `group_square_nested_scale_in_rotate` | match | match |
| `group_opacity` | raises | raises |
| `shape_opacity_times_color_alpha` | match | match |
| `alpha_no_leak` | match | match |
| `text_lato_left` | match | match |
| `text_lato_center` | match | match |
| `text_lato_right` | match | match |
| `text_family_cormorant` | match | match |
| `text_family_cormorant_italic` | match | match |
| `text_family_playfairdisplay` | match | match |
| `text_family_inter` | match | match |
| `text_family_caveat` | match | match |
| `text_family_comfortaa` | match | match |
| `text_family_helvetica` | match | match |
| `text_opacity` | match | match |
| `image_jpeg` | match | match |
| `image_clipped_circle` | match | match |
| `image_opacity` | match | match |
| `fold_line_dashed` | match | match |
| `page_bleed_background` | match | match |
