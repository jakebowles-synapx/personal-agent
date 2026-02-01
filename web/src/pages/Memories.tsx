import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useApi'

interface Memory {
  id: string
  memory: string
  created_at: string | null
  updated_at: string | null
}

export default function Memories() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const { fetchApi } = useApi()

  useEffect(() => {
    loadMemories()
  }, [])

  const loadMemories = async () => {
    setLoading(true)
    const data = await fetchApi<Memory[]>('/api/memories')
    if (data) {
      setMemories(data)
    }
    setLoading(false)
  }

  const deleteMemory = async (id: string) => {
    await fetchApi(`/api/memories/${id}`, { method: 'DELETE' })
    setMemories(prev => prev.filter(m => m.id !== id))
  }

  const clearAllMemories = async () => {
    if (!confirm('Are you sure you want to clear all memories? This cannot be undone.')) {
      return
    }
    await fetchApi('/api/memories', { method: 'DELETE' })
    setMemories([])
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Memories</h1>
        {memories.length > 0 && (
          <button className="btn btn-danger" onClick={clearAllMemories}>
            Clear All
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading">
          <div className="spinner" />
          <span>Loading memories...</span>
        </div>
      ) : memories.length === 0 ? (
        <div className="empty-state" style={{ marginTop: '2rem' }}>
          <p>No memories stored yet.</p>
          <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>
            Memories are automatically extracted from your conversations.
          </p>
        </div>
      ) : (
        <div className="memory-list">
          {memories.map(memory => (
            <div key={memory.id} className="memory-item">
              <div className="memory-content">{memory.memory}</div>
              <button
                className="memory-delete"
                onClick={() => deleteMemory(memory.id)}
                title="Delete memory"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
