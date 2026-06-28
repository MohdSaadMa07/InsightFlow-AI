const BASE = ''

function getHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Token ${token}` } : {}),
  }
}

async function request(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: getHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  })
  let data
  try { data = await res.json() } catch { data = null }
  if (!res.ok) throw new Error(data?.error || (data && typeof data === 'object' ? Object.values(data).flat().join(', ') : `Request failed (${res.status})`))
  return data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),

  auth: {
    signup: (body) =>
      api.post('/api/v1/auth/signup/', body),
    login: (body) =>
      api.post('/api/v1/auth/login/', body),
    me: () => api.get('/api/v1/auth/me/'),
  },

  projects: {
    list: () => api.get('/api/v1/projects/'),
    create: (name) => api.post('/api/v1/projects/', { name }),
    get: (id) => api.get(`/api/v1/projects/${id}/`),
  },

  dashboard: {
    overview: (projectId) => api.get(`/api/v1/dashboard/overview/?project_id=${projectId}`),
    events: (projectId, days = 7) => api.get(`/api/v1/dashboard/events/?project_id=${projectId}&days=${days}`),
    funnels: (projectId, days = 30) => api.get(`/api/v1/dashboard/funnels/?project_id=${projectId}&days=${days}`),
    retention: (projectId) => api.get(`/api/v1/dashboard/retention/?project_id=${projectId}`),
  },

  mapping: {
    list: (projectId) => api.get(`/api/v1/semantic/mappings/?project_id=${projectId}`),
    detect: (projectId) => api.post(`/api/v1/semantic/detect/`, { project_id: projectId }),
    update: (mappingId, data) => api.put(`/api/v1/semantic/mappings/${mappingId}/`, data),
    computeFunnel: (projectId, days = 30) => api.post(`/api/v1/semantic/compute-funnel/`, { project_id: projectId, days }),
  },
}
