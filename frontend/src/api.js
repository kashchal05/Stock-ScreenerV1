import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

export const fetchScreener = (params) =>
  client.get('/screener', { params }).then((r) => r.data)

export const fetchStock = (symbol) =>
  client.get(`/stocks/${symbol}`).then((r) => r.data)

export const fetchHistory = (symbol, range) =>
  client.get(`/stocks/${symbol}/history`, { params: { range } }).then((r) => r.data)

export const fetchIndicators = (symbol) =>
  client.get(`/stocks/${symbol}/indicators`).then((r) => r.data)

export const fetchPrediction = (symbol) =>
  client.get(`/predictions/${symbol}`).then((r) => r.data)

export const fetchModelReport = () =>
  client.get('/model/report').then((r) => r.data)

export const fetchWatchlist = () =>
  client.get('/watchlist').then((r) => r.data)

export const addWatchlistItem = (payload) =>
  client.post('/watchlist', payload).then((r) => r.data)

export const updateWatchlistItem = (id, payload) =>
  client.put(`/watchlist/${id}`, payload).then((r) => r.data)

export const deleteWatchlistItem = (id) =>
  client.delete(`/watchlist/${id}`)

export const fetchMeta = () => client.get('/meta').then((r) => r.data)

export const triggerRefresh = () =>
  client.post('/admin/refresh').then((r) => r.data)

export const fetchRefreshStatus = () =>
  client.get('/admin/refresh/status').then((r) => r.data)
