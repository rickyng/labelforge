import type { AnalyzeResponse, ApplyResponse, AuthResponse, ComponentsResponse, ConfigSummary, ImportJsonResponse, Label, LoadUserLabelResponse, ProfileApplyResponse, ReplaceBarcodeResponse, UploadResponse, UserLabelSummary } from './types'

const BASE = '/api'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as T
  }
  return res.json() as Promise<T>
}

export async function login(username: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  })
  return handleResponse<AuthResponse>(res)
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, { method: 'POST', credentials: 'include' })
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  return handleResponse<UploadResponse>(res)
}

export async function analyzeSession(sessionId: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/analyze/${sessionId}`, {
    method: 'POST',
    credentials: 'include',
  })
  return handleResponse<AnalyzeResponse>(res)
}

export async function applyLabels(
  sessionId: string,
  labels: Label[],
  outputFormat: 'pdf' | 'ai' = 'pdf',
): Promise<ApplyResponse> {
  const res = await fetch(`${BASE}/apply/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ labels, output_format: outputFormat }),
  })
  return handleResponse<ApplyResponse>(res)
}

export async function listConfigs(): Promise<ConfigSummary[]> {
  const res = await fetch(`${BASE}/configs`, { credentials: 'include' })
  return handleResponse(res)
}

export async function loadConfig(filename: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/configs/${encodeURIComponent(filename)}`, { credentials: 'include' })
  return handleResponse<AnalyzeResponse>(res)
}

export async function deleteConfig(filename: string): Promise<void> {
  await fetch(`${BASE}/configs/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
    credentials: 'include',
  })
}

export async function fetchCurrentSession(): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/session/current`, { credentials: 'include' })
  return handleResponse<AnalyzeResponse>(res)
}

export async function saveEditableConfig(sessionId: string, ids: string[], name?: string): Promise<{ saved: number }> {
  const res = await fetch(`${BASE}/editable/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ editable_ids: ids, name: name ?? '' }),
  })
  return handleResponse<{ saved: number }>(res)
}

export async function renameConfig(filename: string, name: string): Promise<void> {
  const res = await fetch(`${BASE}/configs/${encodeURIComponent(filename)}/name`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name }),
  })
  return handleResponse<void>(res)
}

export async function listUserLabels(): Promise<UserLabelSummary[]> {
  const res = await fetch(`${BASE}/labels`, { credentials: 'include' })
  return handleResponse(res)
}

export async function loadUserLabel(name: string): Promise<LoadUserLabelResponse> {
  const res = await fetch(`${BASE}/labels/${encodeURIComponent(name)}`, { credentials: 'include' })
  return handleResponse(res)
}

export async function saveUserLabel(name: string, profileName: string, fills: Record<string, string>): Promise<void> {
  const res = await fetch(`${BASE}/labels/${encodeURIComponent(name)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ profile_name: profileName, fills }),
  })
  return handleResponse<void>(res)
}

export async function deleteUserLabel(name: string): Promise<void> {
  const res = await fetch(`${BASE}/labels/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  return handleResponse<void>(res)
}

export async function analyzeComponents(sessionId: string): Promise<ComponentsResponse> {
  const res = await fetch(`${BASE}/components/${sessionId}`, {
    method: 'POST',
    credentials: 'include',
  })
  return handleResponse<ComponentsResponse>(res)
}

export async function replaceBarcode(
  sessionId: string,
  componentId: string,
  value: string,
  fmt: string,
): Promise<ReplaceBarcodeResponse> {
  const res = await fetch(`${BASE}/components/${sessionId}/${encodeURIComponent(componentId)}/replace-barcode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ value, fmt }),
  })
  return handleResponse<ReplaceBarcodeResponse>(res)
}

export async function applyProfile(
  name: string,
  sizeName: string,
): Promise<ProfileApplyResponse> {
  const res = await fetch(
    `${BASE}/configs/${encodeURIComponent(name)}/apply?size_name=${encodeURIComponent(sizeName)}`,
    { method: 'POST', credentials: 'include' },
  )
  return handleResponse<ProfileApplyResponse>(res)
}

export function previewUrl(sessionId: string): string {
  return `${BASE}/preview/${sessionId}`
}

export function outputPreviewUrl(sessionId: string): string {
  return `${BASE}/output-preview/${sessionId}`
}

export function downloadUrl(sessionId: string): string {
  return `${BASE}/download/${sessionId}`
}

export async function importJson(
  sessionId: string,
  file: File,
): Promise<ImportJsonResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/import-json/${sessionId}`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  return handleResponse<ImportJsonResponse>(res)
}
