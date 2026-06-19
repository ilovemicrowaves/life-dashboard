// Dunne fetch-wrapper. Frontend wordt door de API geserveerd, dus /api is
// same-origin in productie; in dev proxyt Vite /api naar de backend.

const BASE = '/api'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error('GET ' + path + ' -> ' + res.status)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })
  if (!res.ok) throw new Error('POST ' + path + ' -> ' + res.status)
  return res.json()
}

export const api = {
  config: () => get('/config'),
  agenda: () => get('/agenda/today'),
  briefing: (id) => get('/agenda/' + encodeURIComponent(id) + '/briefing'),
  recent: () => get('/logs/recent'),
  log: (text, theme) => post('/log', { text, theme }),
  rebuild: () => post('/index/rebuild'),
  googleStatus: () => get('/auth/google/status'),
  createEvent: (data) => post('/calendar/events', data),
}
