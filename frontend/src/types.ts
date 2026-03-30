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
}

export interface ApplyResponse {
  session_id: string
  changed_count: number
  output_filename: string
  warning: string | null
}

export interface ConfigSummary {
  has_changes: boolean;
  filename: string
  name: string
  editable_count: number
  page_count: number
  file_type: string
  updated_at: string
}

export interface UserLabelSummary {
  name: string
  profile_name: string
  updated_at: string
}

export interface LoadUserLabelResponse extends AnalyzeResponse {
  label_name: string
  profile_name: string
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
}

export interface ComponentsResponse {
  session_id: string
  components: DocumentComponent[]
  page_count: number
}

export interface ReplaceBarcodeResponse {
  session_id: string
  component_id: string
  output_filename: string
}

export interface ProfileApplyResponse {
  session_id: string
  size_name: string
  changed_count: number
  output_filename: string
  warning?: string | null
}

export type Role = 'admin' | 'user'

export interface AuthResponse {
  role: Role
  username: string
}

export type ToastType = 'success' | 'warning' | 'error' | 'info'

export interface Toast {
  id: string
  type: ToastType
  message: string
  leaving?: boolean
}

export interface FieldEntry {
  num: string
  field: string
  path: string
  value: string
  label_id: string
}

export interface ImportJsonResponse {
  session_id: string
  source_file: string
  style_id: string
  color_code: string
  sizes: string[]
  changes_by_size: Record<string, Record<string, string>>
  fields_by_size: Record<string, FieldEntry[]>
}
