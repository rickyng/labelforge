"""Pydantic v2 data models for LabelForge."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1  (top-left origin)

_HEX_RE = re.compile(r"^#[0-9a-f]{6}$")


class Label(BaseModel):
    """Represents one text span extracted from a PDF page.

    ID format: ``p{page}_b{block}_l{line}_s{span}``
    All coordinates use PyMuPDF's top-left origin (y increases downward).
    Colors are stored as lower-case CSS hex strings (``#rrggbb``).

    The ``new_text`` field semantics:
    - ``None``  — leave this span untouched during apply
    - ``""``    — erase the span (redact only, insert nothing)
    - any str   — replace with that string
    """

    id: str = Field(
        ...,
        description="Unique span identifier: p<page>_b<block>_l<line>_s<span>.",
    )
    page: int = Field(..., ge=0, description="0-based page index.")
    bbox: BBox = Field(..., description="[x0, y0, x1, y1] in top-left origin points.")
    original_text: str = Field(..., description="Original text as extracted from the PDF.")
    new_text: str | None = Field(
        default=None,
        description="Replacement text. None=skip, ''=erase only, str=replace.",
    )
    fontname: str = Field(..., description="Font name as reported by PyMuPDF.")
    fontsize: float = Field(..., gt=0, description="Font size in points.")
    color: str = Field(..., description="Text color as #rrggbb hex string.")
    flags: int = Field(default=0, description="Font flags bitmask (bold=16, italic=2).")
    rotation: int = Field(default=0, description="Page rotation in degrees.")
    origin: tuple[float, float] | None = Field(
        default=None,
        description="Baseline origin point (x, y) from PyMuPDF span. Used for pixel-perfect vertical alignment.",
    )
    block_index: int = Field(default=0, ge=0)
    line_index: int = Field(default=0, ge=0)
    span_index: int = Field(default=0, ge=0)
    auto_fit: bool = Field(
        default=True,
        description="Use insert_htmlbox with scale_low for automatic overflow prevention.",
    )
    max_scale_down: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum font scale factor (0.0=unlimited shrink, 1.0=no shrink).",
    )
    padding: float = Field(
        default=0.0,
        ge=0.0,
        description="Inset the insertion rect by this many points on each side for safety.",
    )
    white_out: bool = Field(
        default=False,
        description="Draw a white fill rect over the redacted area before inserting text. Disable if borders overlap the label bbox.",
    )

    model_config = {"frozen": False}

    @field_validator("color", mode="before")
    @classmethod
    def normalise_color(cls, v: Any) -> str:  # noqa: ANN401
        """Accept packed int or hex string, always return #rrggbb."""
        if isinstance(v, int):
            return f"#{max(0, v) & 0xFFFFFF:06x}"
        if isinstance(v, str):
            s = v.strip().lower()
            if not s.startswith("#"):
                s = "#" + s
            if not _HEX_RE.match(s):
                raise ValueError(f"Invalid color string: {v!r}")
            return s
        raise ValueError(f"Color must be int or hex string, got {type(v)}")

    @field_validator("bbox", mode="before")
    @classmethod
    def validate_bbox(cls, v: Any) -> BBox:  # noqa: ANN401
        """Ensure bbox is a 4-float tuple with non-negative area."""
        seq = tuple(float(x) for x in v)
        if len(seq) != 4:
            raise ValueError("bbox must have exactly 4 values")
        x0, y0, x1, y1 = seq
        if x1 < x0 or y1 < y0:
            raise ValueError(f"bbox has negative dimensions: {seq}")
        return seq  # type: ignore[return-value]

    @property
    def is_changed(self) -> bool:
        """True if this label has a pending edit to apply."""
        return self.new_text is not None and self.new_text != self.original_text

    @property
    def effective_text(self) -> str:
        """The text that should appear in the output PDF."""
        return self.new_text if self.new_text is not None else self.original_text
