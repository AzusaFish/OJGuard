const API_ROOT = '/api/v1'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(payload.detail || payload.message || `请求失败 (${response.status})`, response.status)
  }
  return payload as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  upload: <T>(path: string, body: FormData) => request<T>(path, { method: 'POST', body }),
}
