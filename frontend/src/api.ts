export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

let adminCsrf = ''
const participantCsrf = new Map<number, string>()

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const editionMatch = path.match(/^\/editions\/(\d+)\/answers$/)
  const csrf = editionMatch ? participantCsrf.get(Number(editionMatch[1])) : adminCsrf
  const response = await fetch(`/api/v1${path}`, {
    method, credentials: 'same-origin',
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(csrf ? { 'X-CSRF-Token': csrf } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  if (response.status === 204) return undefined as T
  const data = await response.json()
  if (!response.ok) {
    const details = Array.isArray(data.errors) ? ` ${data.errors.map((e: { message: string }) => e.message).join(' ')}` : ''
    throw new ApiError(response.status, (typeof data.detail === 'string' ? data.detail : 'Cererea nu a putut fi procesată.') + details)
  }
  if (data.csrf) {
    if (path.startsWith('/admin/') || path.startsWith('/auth/')) adminCsrf = data.csrf
    else {
      const match = path.match(/^\/editions\/(\d+)\//)
      if (match) participantCsrf.set(Number(match[1]), data.csrf)
    }
  }
  if (path === '/admin/logout' || path === '/auth/logout') { adminCsrf = ''; participantCsrf.clear() }
  return data as T
}
