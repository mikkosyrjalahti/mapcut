"""Single-stroke engraving font.

Laser line-engraving wants one stroke per glyph line; outline (TTF) text would engrave as
double contours or need a fill pass, and DXF TEXT entities import unreliably into CAM tools.
"""

from __future__ import annotations

# Glyphs on a 4 wide x 6 high grid, origin at the baseline-left.
_GLYPHS: dict[str, list[list[tuple[float, float]]]] = {
    "0": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)]],
    "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 6), (4, 6), (4, 3), (0, 3), (0, 0), (4, 0)]],
    "3": [[(0, 6), (4, 6), (4, 0), (0, 0)], [(1, 3), (4, 3)]],
    "4": [[(0, 6), (0, 3), (4, 3)], [(4, 6), (4, 0)]],
    "5": [[(4, 6), (0, 6), (0, 3), (4, 3), (4, 0), (0, 0)]],
    "6": [[(4, 6), (0, 6), (0, 0), (4, 0), (4, 3), (0, 3)]],
    "7": [[(0, 6), (4, 6), (1, 0)]],
    "8": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(0, 3), (4, 3)]],
    "9": [[(4, 3), (0, 3), (0, 6), (4, 6), (4, 0), (0, 0)]],
    "-": [[(1, 3), (3, 3)]],
    ".": [[(1.5, 0), (2.5, 0)]],
    "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "W": [[(0, 6), (1, 0), (2, 3), (3, 0), (4, 6)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 2)], [(1.5, 3.5), (4, 0)]],
    " ": [],
}
_ADVANCE = 5.5  # glyph width 4 + gap 1.5 grid units


def width(text: str, height: float) -> float:
    return (len(text) * _ADVANCE - (_ADVANCE - 4)) * height / 6


def render(text: str, x: float, y: float, height: float) -> list[list[tuple[float, float]]]:
    """Polylines for `text` with its baseline-left corner at (x, y)."""
    s = height / 6
    out = []
    for n, ch in enumerate(text):
        dx = x + n * _ADVANCE * s
        for stroke in _GLYPHS[ch]:
            out.append([(dx + gx * s, y + gy * s) for gx, gy in stroke])
    return out
