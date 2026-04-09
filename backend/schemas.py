"""Pydantic v2 API schemas for LabelForge Web."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LabelDTO(BaseModel):
    """Wire representation of a Label — mirrors labelforge.models.Label."""

    id: str
    page: int
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    original_text: str
    new_text: str | None = None
    fontname: str
    fontsize: float
    color: str
    flags: int = 0
    rotation: int = 0
    origin: list[float] | None = None
    auto_fit: bool = True
    max_scale_down: float = 0.5
    padding: float = 0.0
    white_out: bool = False


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    file_type: str  # "json"
    warning: str | None = None


class AnalyzeResponse(BaseModel):
    session_id: str
    labels: list[LabelDTO]
    page_count: int
    file_type: str
    editable_ids: list[str] = []
    warning: str | None = None
    changes_data: dict | None = None
    mapping_name: str | None = None


class ApplyRequest(BaseModel):
    labels: list[LabelDTO]
    output_format: Literal["pdf", "ai"] = "pdf"


class ApplyResponse(BaseModel):
    session_id: str
    changed_count: int
    output_filename: str
    warning: str | None = None


class ConfigSummary(BaseModel):
    filename: str
    name: str
    editable_count: int
    page_count: int
    file_type: str
    updated_at: str
    has_changes: bool = False


class UserLabelSummary(BaseModel):
    name: str
    profile_name: str
    updated_at: str


class SaveUserLabelBody(BaseModel):
    profile_name: str
    fills: dict[str, str]  # label_id -> new_text


class LoadUserLabelResponse(AnalyzeResponse):
    label_name: str
    profile_name: str


# --- Component extraction schemas ---

class ComponentDTO(BaseModel):
    """Wire representation of a DocumentComponent."""

    id: str
    type: str                                    # ComponentType value string
    page: int
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    xref: int | None = None
    text: str | None = None
    fontname: str | None = None
    fontsize: float | None = None
    color: str | None = None
    image_format: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    thumbnail_b64: str | None = None
    barcode_value: str | None = None
    barcode_format: str | None = None           # BarcodeFormat value string
    editable: bool = True

    # SHAPE-specific fields
    fill_color: str | None = None               # "#rrggbb" hex or None
    fill_opacity: float | None = None           # 0.0-1.0
    stroke_color: str | None = None             # "#rrggbb" hex or None
    stroke_width: float | None = None           # line width in points


class ComponentsResponse(BaseModel):
    session_id: str
    components: list[ComponentDTO]
    page_count: int


class ReplaceBarcodeRequest(BaseModel):
    value: str
    fmt: str                                     # BarcodeFormat value string


class ReplaceBarcodeResponse(BaseModel):
    session_id: str
    component_id: str
    output_filename: str


class SizeChanges(BaseModel):
    size_name: str
    changes: dict[str, str]  # component_id -> new_value


class ChangesData(BaseModel):
    source_file: str
    style_id: str
    color_code: str
    generated_at: str
    sizes: list[SizeChanges]


class ProfileApplyResponse(BaseModel):
    session_id: str
    size_name: str
    changed_count: int
    output_filename: str
    warning: str | None = None


# --- Template mapping schemas ---


class TemplateSummary(BaseModel):
    name: str
    field_count: int


class TemplatesListResponse(BaseModel):
    templates: list[TemplateSummary]


class TemplateField(BaseModel):
    id: str
    pdf_reference: str
    json_path: str
    field_type: str  # "single" | "per_size" | "unmapped"


class TemplateFieldsResponse(BaseModel):
    template_name: str
    fields: list[TemplateField]


class ResolvedField(BaseModel):
    id: str
    pdf_reference: str
    json_path: str
    field_type: str
    values: list[str | None]


class ResolvedFieldsResponse(BaseModel):
    template_name: str
    size_count: int
    size_names: list[str]
    fields: list[ResolvedField]
    changes: list[dict[str, str]] | None = None


class ComponentMapResponse(BaseModel):
    template_name: str
    size_count: int
    size_names: list[str]
    fields: list[ResolvedField]
    changes: list[dict[str, str]]
