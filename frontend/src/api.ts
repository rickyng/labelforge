import type { AnalyzeResponse, ComponentMapResponse, ComponentsResponse, ProfileApplyResponse, TemplatesListResponse, UploadResponse } from './types'

const BASE = '/api'
const DEFAULT_TIMEOUT_MS = 30_000
const LONG_TIMEOUT_MS = 120_000

function fetchWithTimeout(url: string, init: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController()
  const id = setTimeout(() => controller.abort(), timeoutMs)
  return fetch(url, { ...init, signal: controller.signal }).finally(() => clearTimeout(id))
}

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

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetchWithTimeout(`${BASE}/upload`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  }, LONG_TIMEOUT_MS)
  return handleResponse<UploadResponse>(res)
}

export async function analyzeComponents(sessionId: string): Promise<ComponentsResponse> {
  const res = await fetchWithTimeout(`${BASE}/components/${sessionId}`, {
    method: 'POST',
    credentials: 'include',
  })
  return handleResponse<ComponentsResponse>(res)
}

export function previewUrl(sessionId: string): string {
  return `${BASE}/preview/${sessionId}`
}

export function previewImagesUrl(sessionId: string): string {
  return `${BASE}/preview-images/${sessionId}`
}

export function outputPreviewUrl(sessionId: string): string {
  return `${BASE}/output-preview/${sessionId}`
}

export function downloadUrl(sessionId: string): string {
  return `${BASE}/download/${sessionId}`
}

export async function listTemplates(): Promise<TemplatesListResponse> {
  const res = await fetchWithTimeout(`${BASE}/templates`, { credentials: 'include' })
  return handleResponse<TemplatesListResponse>(res)
}

export async function mapTemplateFields(templateName: string, file: File, sessionId?: string): Promise<ComponentMapResponse> {
  const form = new FormData()
  form.append('file', file)
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
  const res = await fetchWithTimeout(`${BASE}/templates/${encodeURIComponent(templateName)}/map${query}`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  return handleResponse<ComponentMapResponse>(res)
}

export async function loadAiFile(templateName: string, sessionId: string): Promise<AnalyzeResponse> {
  const res = await fetchWithTimeout(
    `${BASE}/templates/${encodeURIComponent(templateName)}/load-ai?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'POST', credentials: 'include' },
    LONG_TIMEOUT_MS,
  )
  return handleResponse<AnalyzeResponse>(res)
}

export async function applyDirect(
  templateName: string,
  sessionId: string,
  sizeIndex: number,
): Promise<ProfileApplyResponse> {
  const res = await fetchWithTimeout(
    `${BASE}/templates/${encodeURIComponent(templateName)}/apply-direct?session_id=${encodeURIComponent(sessionId)}&size_index=${sizeIndex}`,
    { method: 'POST', credentials: 'include' },
    LONG_TIMEOUT_MS,
  )
  return handleResponse<ProfileApplyResponse>(res)
}

export async function fetchSampleOrder(): Promise<{ file: File; data: unknown }> {
  const res = await fetchWithTimeout(`${BASE}/sample-order`, { credentials: 'include' })
  const data = await handleResponse<unknown>(res)
  const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
  const file = new File([blob], '4500801837-00000017-205456MK26.json', { type: 'application/json' })
  return { file, data }
}
