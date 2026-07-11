export default function ErrorBanner({ error }) {
  if (!error) return null
  const message =
    typeof error === 'string' ? error : error.response?.data?.detail || error.message || 'Something went wrong'
  return <div className="error-banner">{message}</div>
}
