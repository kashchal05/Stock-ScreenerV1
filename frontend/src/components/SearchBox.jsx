import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchTickers } from '../api.js'

export default function SearchBox() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const boxRef = useRef(null)

  // Debounced search — all state updates happen inside the timeout callback,
  // never synchronously in the effect body.
  useEffect(() => {
    const q = query.trim()
    const id = setTimeout(() => {
      if (q.length < 1) {
        setResults([])
        setOpen(false)
        return
      }
      searchTickers(q)
        .then((rows) => {
          setResults(rows)
          setOpen(true)
          setActive(0)
        })
        .catch(() => setResults([]))
    }, 180)
    return () => clearTimeout(id)
  }, [query])

  // Close on outside click
  useEffect(() => {
    const onClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const go = (symbol) => {
    setQuery('')
    setResults([])
    setOpen(false)
    navigate(`/stocks/${symbol}`)
  }

  const onKeyDown = (e) => {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      go(results[active].symbol)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="search-box" ref={boxRef}>
      <input
        type="text"
        placeholder="Search ticker…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        onKeyDown={onKeyDown}
        aria-label="Search stocks"
      />
      {open && results.length > 0 && (
        <ul className="search-results">
          {results.map((r, i) => (
            <li
              key={r.symbol}
              className={i === active ? 'active' : ''}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault()
                go(r.symbol)
              }}
            >
              <span className="sym">{r.symbol}</span>
              <span className="nm">{r.name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
