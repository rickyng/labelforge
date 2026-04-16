export interface Label {
  id: string
  page: number
  bbox: [number, number, number, number] // x0, y0, x1, y1
  original_text: string
  new_text: string | null
  fontname: string
  fontsize: number
  color: string
  flags: number
  rotation: number
  origin: [number, number] | null
  auto_fit: boolean
  max_scale_down: number
  padding: number
  white_out: boolean
}

export interface UploadResponse {
  session_id: string
  filename: string
  file_type: string
  warning: string | null
}

export interface AnalyzeResponse {
  session_id: string
  labels: Label[]
  page_count: number
  file_type: string
  editable_ids: string[]
  warning: string | null
  mapping_name?: string | null
  grouping_mode: 'span' | 'line' | 'block'
}

export type ComponentType = 'TEXT' | 'IMAGE' | 'BARCODE' | 'SHAPE'

export type BarcodeFormat = 'ean13' | 'ean8' | 'code128' | 'code39' | 'qr' | 'upca'

export interface DocumentComponent {
  id: string
  type: ComponentType
  page: number
  bbox: [number, number, number, number]
  xref: number | null
  text: string | null
  fontname: string | null
  fontsize: number | null
  color: string | null
  image_format: string | null
  width_px: number | null
  height_px: number | null
  thumbnail_b64: string | null
  barcode_value: string | null
  barcode_format: BarcodeFormat | null
  editable: boolean
  // SHAPE-specific fields
  fill_color: string | null
  fill_opacity: number | null
  stroke_color: string | null
  stroke_width: number | null

  // OCR fields (for SHAPE components with detected outlined text)
  ocr_text: string | null
  ocr_confidence: number | null
  ocr_language: string | null
}

export interface ComponentsResponse {
  session_id: string
  components: DocumentComponent[]
  page_count: number
}

export interface ProfileApplyResponse {
  session_id: string
  size_name: string
  changed_count: number
  output_filename: string
  warning?: string | null
}

export type ToastType = 'success' | 'warning' | 'error' | 'info'

export interface Toast {
  id: string
  type: ToastType
  message: string
  leaving?: boolean
}

export interface TemplateSummary {
  name: string
  field_count: number
  label_id?: string | null
  grouping_mode: 'span' | 'line' | 'block'
}

export interface TemplatesListResponse {
  templates: TemplateSummary[]
}

export interface ResolvedField {
  id: string
  pdf_reference: string
  json_path: string
  field_type: 'single' | 'per_size' | 'unmapped'
  values: (string | null)[]
}

export interface ComponentMapResponse {
  template_name: string
  size_count: number
  size_names: string[]
  fields: ResolvedField[]
  changes: Record<string, string>[]
}
