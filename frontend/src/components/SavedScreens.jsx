import { useCallback, useEffect, useState } from 'react'
import { deleteSavedScreen, fetchSavedScreens, saveScreen } from '../api.js'

// Lets the user save the current filter/sort (the URL query string) under a name
// and reload or delete it later. `currentQuery` is the live search string; `onLoad`
// applies a saved query back to the screener.
export default function SavedScreens({ currentQuery, onLoad }) {
  const [screens, setScreens] = useState([])

  const load = useCallback(() => {
    fetchSavedScreens().then(setScreens).catch(() => setScreens([]))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const onSave = async () => {
    const name = window.prompt('Name this screen:')
    if (!name || !name.trim()) return
    try {
      await saveScreen(name.trim(), currentQuery)
      load()
    } catch {
      /* ignore */
    }
  }

  const onDelete = async (e, id) => {
    e.stopPropagation()
    await deleteSavedScreen(id)
    load()
  }

  return (
    <div className="saved-screens">
      <button className="secondary" onClick={onSave} disabled={!currentQuery}>
        ★ Save this screen
      </button>
      {screens.map((s) => (
        <button
          key={s.id}
          className="chip saved-chip"
          onClick={() => onLoad(s.query)}
          title={`Load: ${s.query || '(no filters)'}`}
        >
          {s.name}
          <span className="del" onClick={(e) => onDelete(e, s.id)} title="Delete">
            ✕
          </span>
        </button>
      ))}
    </div>
  )
}
