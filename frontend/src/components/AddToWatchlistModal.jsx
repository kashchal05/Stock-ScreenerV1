import { useState } from 'react'
import { addWatchlistItem, updateWatchlistItem } from '../api.js'
import ErrorBanner from './ErrorBanner.jsx'

export default function AddToWatchlistModal({ symbol, item, onClose, onSaved }) {
  const editing = Boolean(item)
  const [buyPrice, setBuyPrice] = useState(item?.buy_price ?? '')
  const [quantity, setQuantity] = useState(item?.quantity ?? '')
  const [notes, setNotes] = useState(item?.notes ?? '')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    const payload = {
      buy_price: buyPrice === '' ? null : Number(buyPrice),
      quantity: quantity === '' ? null : Number(quantity),
      notes: notes || null,
    }
    try {
      if (editing) {
        await updateWatchlistItem(item.id, payload)
      } else {
        await addWatchlistItem({ symbol, ...payload })
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2 style={{ margin: 0 }}>
          {editing ? `Edit ${item.symbol}` : `Add ${symbol} to watchlist`}
        </h2>
        <ErrorBanner error={error} />
        <div className="field">
          <label htmlFor="buy-price">Buy price (optional)</label>
          <input
            id="buy-price"
            type="number"
            step="any"
            min="0"
            value={buyPrice}
            onChange={(e) => setBuyPrice(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="quantity">Quantity (optional)</label>
          <input
            id="quantity"
            type="number"
            step="any"
            min="0"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="notes">Notes</label>
          <textarea id="notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </div>
  )
}
