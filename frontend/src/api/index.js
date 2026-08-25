import axios from 'axios'

const http = axios.create({ timeout: 30000 })

http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export const serversApi = {
  list: () => http.get('/api/servers'),
  get: (id) => http.get(`/api/servers/${id}`),
  gpus: (id) => http.get(`/api/servers/${id}/gpus`),
  createManual: (data) => http.post('/api/servers/manual', data),
  update: (id, data) => http.put(`/api/servers/${id}`, data),
  remove: (id) => http.delete(`/api/servers/${id}`),
}

export const modelsApi = {
  list: () => http.get('/api/models'),
  create: (data) => http.post('/api/models', data),
  import: (data) => http.post('/api/models/import', data),
  prequantized: (data) => http.post('/api/models/prequantized', data),
  addVersion: (id, data) => http.post(`/api/models/${id}/versions`, data),
}

export const enginesApi = {
  list: () => http.get('/api/engines'),
}

export const fsApi = {
  roots: () => http.get('/api/fs/roots'),
  list: (path) => http.get('/api/fs/list', { params: { path } }),
  inspect: (path) => http.get('/api/fs/inspect', { params: { path } }),
}

export const recommendApi = {
  recommend: (data) => http.post('/api/recommend', data),
  plan: (data) => http.post('/api/recommend/plan', data),
  models: (serverId) => http.get('/api/recommend/models', { params: { server_id: serverId } }),
}

export const deploymentsApi = {
  list: () => http.get('/api/deployments'),
  create: (data) => http.post('/api/deployments', data),
  stop: (id) => http.post(`/api/deployments/${id}/stop`),
  restart: (id) => http.post(`/api/deployments/${id}/restart`),
  scale: (id, replicas) => http.post(`/api/deployments/${id}/scale`, { replicas }),
}

export const quantizeApi = {
  list: () => http.get('/api/quantize'),
  create: (data) => http.post('/api/quantize', data),
}

export const hfApi = {
  search: (params) => http.get('/api/hf/search', { params }),
  orgs: () => http.get('/api/hf/orgs'),
  orgModels: (org, params) => http.get(`/api/hf/org/${org}`, { params }),
  files: (repoId) => http.get(`/api/hf/models/${repoId}/files`),
  download: (data) => http.post('/api/hf/download', data),
  downloads: () => http.get('/api/hf/downloads'),
  downloadDetail: (id) => http.get(`/api/hf/downloads/${id}`),
}

export const monitorApi = {
  overview: () => http.get('/api/monitor/overview'),
  alerts: (openOnly = false) => http.get('/api/monitor/alerts', { params: { open_only: openOnly } }),
  ack: (id) => http.post(`/api/monitor/alerts/${id}/ack`),
}
