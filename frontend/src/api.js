const BASE = import.meta.env.VITE_API_URL || 'https://98.93.48.72.nip.io'

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
    keys: (id) => api.get(`/api/v1/projects/${id}/keys/`),
    regenerateKey: (id) => api.post(`/api/v1/projects/${id}/regenerate-key/`),
  },

  dashboard: {
    overview: (projectId) => api.get(`/api/v1/dashboard/overview/?project_id=${projectId}`),
    events: (projectId, days = 7, startDate, endDate) => {
      let url = `/api/v1/dashboard/events/?project_id=${projectId}`
      if (startDate && endDate) url += `&start_date=${startDate}&end_date=${endDate}`
      else url += `&days=${days}`
      return api.get(url)
    },
    funnels: (projectId, days = 30, startDate, endDate) => {
      let url = `/api/v1/dashboard/funnels/?project_id=${projectId}`
      if (startDate && endDate) url += `&start_date=${startDate}&end_date=${endDate}`
      else url += `&days=${days}`
      return api.get(url)
    },
    retention: (projectId) => api.get(`/api/v1/dashboard/retention/?project_id=${projectId}`),
    realtime: (projectId) => api.get(`/api/v1/dashboard/realtime/?project_id=${projectId}`),
    pages: (projectId, days = 7) => api.get(`/api/v1/dashboard/pages/?project_id=${projectId}&days=${days}`),
    countries: (projectId) => api.get(`/api/v1/dashboard/countries/?project_id=${projectId}`),
    devices: (projectId) => api.get(`/api/v1/dashboard/devices/?project_id=${projectId}`),
    sessions: (projectId) => api.get(`/api/v1/dashboard/sessions/?project_id=${projectId}`),
    insights: (projectId) => api.get(`/api/v1/dashboard/insights/?project_id=${projectId}`),
    anomalies: (projectId, days = 14, userId) => {
      let url = `/api/v1/dashboard/anomalies/?project_id=${projectId}&days=${days}`
      if (userId) url += `&user_id=${userId}`
      return api.get(url)
    },
  },

  mapping: {
    list: (projectId) => api.get(`/api/v1/semantic/mappings/?project_id=${projectId}`),
    detect: (projectId) => api.post(`/api/v1/semantic/detect/`, { project_id: projectId }),
    update: (mappingId, data) => api.put(`/api/v1/semantic/mappings/${mappingId}/`, data),
    computeFunnel: (projectId, days = 30) => api.post(`/api/v1/semantic/compute-funnel/`, { project_id: projectId, days }),
  },
}
