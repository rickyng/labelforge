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
