export default function EmptyState({ title, children }) {
  return (
    <div className="state">
      <p style={{ fontWeight: 600, color: 'var(--text)' }}>{title}</p>
      {children}
    </div>
  )
}
