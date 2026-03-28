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
    file_type: str  # "pdf" or "ai"
    warning: str | None = None


class AnalyzeResponse(BaseModel):
    session_id: str
    labels: list[LabelDTO]
    page_count: int
    file_type: str
    editable_ids: list[str] = []
    warning: str | None = None


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


class AuthRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    role: Literal["admin", "user"]
    username: str


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
