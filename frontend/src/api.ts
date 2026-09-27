const BASE = import.meta.env.VITE_API_URL !== undefined
  ? import.meta.env.VITE_API_URL
  : (import.meta.env.PROD ? '' : 'http://localhost:8081')
export const API_BASE = BASE

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI returns `detail` as a string OR (for 422) an array of error objects.
function detailToMessage(body: unknown, fallback: string): string {
  const d = (body as any)?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e: any) => e?.msg ?? JSON.stringify(e)).join('; ')
  return fallback
}

export function getToken(): string | null {
  return localStorage.getItem('diris_token')
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem('diris_token', token)
  else localStorage.removeItem('diris_token')
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (opts.body && !(opts.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (res.status === 401) {
    setToken(null)
    throw new ApiError(401, 'Session expired — please log in again.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, detailToMessage(body, res.statusText))
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') || ''
  return (ct.includes('application/json') ? res.json() : res.text()) as Promise<T>
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: 'POST', body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined }),
  put: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: 'PUT', body: body instanceof FormData ? body : JSON.stringify(body) }),
  del: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
}

// Auth: /auth/login expects an OAuth2 form (username/password); register is JSON.
export async function loginRequest(email: string, password: string): Promise<string> {
  const form = new URLSearchParams()
  form.set('username', email)
  form.set('password', password)
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, detailToMessage(body, 'Login failed'))
  }
  const data = await res.json()
  return data.access_token as string
}

export async function registerRequest(email: string, password: string): Promise<void> {
  await request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) })
}
