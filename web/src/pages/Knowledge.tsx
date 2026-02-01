import { useState, useEffect, useRef } from 'react'
import { useApi } from '../hooks/useApi'

interface KnowledgeItem {
  id: number
  category: string
  title: string
  content: string
  source: string | null
  created_at: string
  updated_at: string
}

interface CategoryCount {
  [key: string]: number
}

const CATEGORIES = ['strategy', 'team', 'processes', 'clients', 'projects']

export default function Knowledge() {
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [stats, setStats] = useState<{ total: number; by_category: CategoryCount }>({ total: 0, by_category: {} })
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedItem, setSelectedItem] = useState<KnowledgeItem | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { fetchApi } = useApi()

  // Form state
  const [formTitle, setFormTitle] = useState('')
  const [formContent, setFormContent] = useState('')
  const [formCategory, setFormCategory] = useState('team')

  useEffect(() => {
    loadData()
  }, [selectedCategory])

  const loadData = async () => {
    setLoading(true)
    const params = selectedCategory ? `?category=${selectedCategory}` : ''
    const [itemsData, statsData] = await Promise.all([
      fetchApi<KnowledgeItem[]>(`/api/knowledge${params}`),
      fetchApi<{ total: number; by_category: CategoryCount }>('/api/knowledge/stats'),
    ])
    if (itemsData) setItems(itemsData)
    if (statsData) setStats(statsData)
    setLoading(false)
  }

  const addKnowledge = async () => {
    if (!formTitle.trim() || !formContent.trim()) return

    const newItem = await fetchApi<KnowledgeItem>('/api/knowledge', {
      method: 'POST',
      body: { title: formTitle, content: formContent, category: formCategory },
    })

    if (newItem) {
      setItems(prev => [newItem, ...prev])
      setStats(prev => ({
        total: prev.total + 1,
        by_category: {
          ...prev.by_category,
          [formCategory]: (prev.by_category[formCategory] || 0) + 1,
        },
      }))
      setShowAddForm(false)
      setFormTitle('')
      setFormContent('')
    }
  }

  const deleteItem = async (id: number) => {
    if (!confirm('Delete this knowledge item?')) return

    await fetchApi(`/api/knowledge/${id}`, { method: 'DELETE' })
    const deleted = items.find(i => i.id === id)
    setItems(prev => prev.filter(i => i.id !== id))
    if (deleted) {
      setStats(prev => ({
        total: prev.total - 1,
        by_category: {
          ...prev.by_category,
          [deleted.category]: Math.max(0, (prev.by_category[deleted.category] || 0) - 1),
        },
      }))
    }
    if (selectedItem?.id === id) {
      setSelectedItem(null)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', formCategory)

    try {
      const response = await fetch('/api/knowledge/upload', {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const newItem = await response.json()
        setItems(prev => [newItem, ...prev])
        setStats(prev => ({
          total: prev.total + 1,
          by_category: {
            ...prev.by_category,
            [formCategory]: (prev.by_category[formCategory] || 0) + 1,
          },
        }))
        setShowAddForm(false)
      } else {
        const error = await response.json()
        alert(error.detail || 'Upload failed')
      }
    } catch (err) {
      alert('Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleDateString([], {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'strategy': return '🎯'
      case 'team': return '👥'
      case 'processes': return '⚙️'
      case 'clients': return '🤝'
      case 'projects': return '📁'
      default: return '📄'
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: '1200px' }}>
      <div className="page-header">
        <h1 className="page-title">Knowledge Base</h1>
        <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
          + Add Knowledge
        </button>
      </div>

      {/* Category tabs */}
      <div className="category-tabs">
        <button
          className={`category-tab ${selectedCategory === null ? 'active' : ''}`}
          onClick={() => setSelectedCategory(null)}
        >
          All ({stats.total})
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            className={`category-tab ${selectedCategory === cat ? 'active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {getCategoryIcon(cat)} {cat.charAt(0).toUpperCase() + cat.slice(1)} ({stats.by_category[cat] || 0})
          </button>
        ))}
      </div>

      <div className="knowledge-layout">
        {/* List */}
        <div className="knowledge-list-panel">
          {loading ? (
            <div className="loading" style={{ padding: '2rem' }}>
              <div className="spinner" />
              <span>Loading...</span>
            </div>
          ) : items.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>No knowledge items found</p>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Add documents or text to build your knowledge base
              </p>
            </div>
          ) : (
            <div className="knowledge-list">
              {items.map(item => (
                <div
                  key={item.id}
                  className={`knowledge-item ${selectedItem?.id === item.id ? 'selected' : ''}`}
                  onClick={() => setSelectedItem(item)}
                >
                  <div className="knowledge-icon">{getCategoryIcon(item.category)}</div>
                  <div className="knowledge-content">
                    <div className="knowledge-title">{item.title}</div>
                    <div className="knowledge-meta">
                      <span className="knowledge-category">{item.category}</span>
                      {item.source && <span className="knowledge-source">{item.source}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail */}
        <div className="knowledge-detail-panel">
          {selectedItem ? (
            <div className="knowledge-detail">
              <div className="detail-header">
                <span className="detail-category">
                  {getCategoryIcon(selectedItem.category)} {selectedItem.category}
                </span>
                <button className="btn btn-danger btn-sm" onClick={() => deleteItem(selectedItem.id)}>
                  Delete
                </button>
              </div>
              <h2 className="detail-title">{selectedItem.title}</h2>
              <div className="detail-meta">
                {selectedItem.source && <span>Source: {selectedItem.source}</span>}
                <span>Updated: {formatDate(selectedItem.updated_at)}</span>
              </div>
              <div className="detail-content">
                {selectedItem.content.split('\n').map((line, i) => (
                  <p key={i}>{line || '\u00A0'}</p>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>Select an item to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Add Form Modal */}
      {showAddForm && (
        <div className="modal-overlay" onClick={() => setShowAddForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>Add Knowledge</h2>

            <div className="form-group">
              <label>Category</label>
              <select value={formCategory} onChange={e => setFormCategory(e.target.value)}>
                {CATEGORIES.map(cat => (
                  <option key={cat} value={cat}>
                    {getCategoryIcon(cat)} {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Title</label>
              <input
                type="text"
                value={formTitle}
                onChange={e => setFormTitle(e.target.value)}
                placeholder="Enter a title"
              />
            </div>

            <div className="form-group">
              <label>Content</label>
              <textarea
                value={formContent}
                onChange={e => setFormContent(e.target.value)}
                placeholder="Enter the knowledge content..."
                rows={8}
              />
            </div>

            <div className="form-divider">
              <span>or upload a document</span>
            </div>

            <div className="upload-area">
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.docx,.pdf"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
              />
              <button
                className="btn btn-outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? 'Uploading...' : 'Upload Document'}
              </button>
              <span className="upload-hint">Supports: .txt, .md, .docx, .pdf</span>
            </div>

            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setShowAddForm(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={addKnowledge}
                disabled={!formTitle.trim() || !formContent.trim()}
              >
                Add Knowledge
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .category-tabs {
          display: flex;
          gap: 0.5rem;
          margin-bottom: 1rem;
          flex-wrap: wrap;
        }
        .category-tab {
          padding: 0.5rem 1rem;
          background-color: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 9999px;
          font-size: 0.875rem;
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.15s;
        }
        .category-tab:hover {
          border-color: var(--accent);
          color: var(--text-primary);
        }
        .category-tab.active {
          background-color: var(--accent);
          border-color: var(--accent);
          color: white;
        }
        .knowledge-layout {
          display: grid;
          grid-template-columns: 400px 1fr;
          gap: 1rem;
          height: calc(100vh - 250px);
          min-height: 400px;
        }
        @media (max-width: 900px) {
          .knowledge-layout {
            grid-template-columns: 1fr;
          }
        }
        .knowledge-list-panel {
          background-color: var(--bg-secondary);
          border-radius: 8px;
          overflow-y: auto;
        }
        .knowledge-list {
          padding: 0.5rem;
        }
        .knowledge-item {
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
          padding: 0.75rem;
          border-radius: 6px;
          cursor: pointer;
          transition: background-color 0.15s;
        }
        .knowledge-item:hover {
          background-color: var(--bg-tertiary);
        }
        .knowledge-item.selected {
          background-color: var(--bg-tertiary);
        }
        .knowledge-icon {
          font-size: 1.25rem;
        }
        .knowledge-content {
          flex: 1;
          min-width: 0;
        }
        .knowledge-title {
          font-size: 0.875rem;
          font-weight: 500;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .knowledge-meta {
          font-size: 0.75rem;
          color: var(--text-secondary);
          display: flex;
          gap: 0.5rem;
          margin-top: 0.25rem;
        }
        .knowledge-category {
          text-transform: capitalize;
        }
        .knowledge-source {
          opacity: 0.7;
        }
        .knowledge-detail-panel {
          background-color: var(--bg-secondary);
          border-radius: 8px;
          overflow-y: auto;
        }
        .knowledge-detail {
          padding: 1.5rem;
        }
        .detail-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }
        .detail-category {
          font-size: 0.875rem;
          color: var(--text-secondary);
          text-transform: capitalize;
        }
        .detail-title {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 0.5rem;
        }
        .detail-meta {
          font-size: 0.75rem;
          color: var(--text-secondary);
          display: flex;
          gap: 1rem;
          margin-bottom: 1.5rem;
        }
        .detail-content {
          font-size: 0.9375rem;
          line-height: 1.6;
        }
        .detail-content p {
          margin-bottom: 0.5rem;
        }
        .btn-sm {
          padding: 0.25rem 0.75rem;
          font-size: 0.75rem;
        }
        .modal-overlay {
          position: fixed;
          inset: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 1rem;
        }
        .modal {
          background-color: var(--bg-secondary);
          border-radius: 12px;
          padding: 1.5rem;
          width: 100%;
          max-width: 500px;
          max-height: 90vh;
          overflow-y: auto;
        }
        .modal h2 {
          margin-bottom: 1.5rem;
        }
        .form-group {
          margin-bottom: 1rem;
        }
        .form-group label {
          display: block;
          font-size: 0.875rem;
          font-weight: 500;
          margin-bottom: 0.5rem;
        }
        .form-group input, .form-group select, .form-group textarea {
          width: 100%;
          padding: 0.75rem;
          background-color: var(--bg-primary);
          border: 1px solid var(--border);
          border-radius: 6px;
          color: var(--text-primary);
          font-size: 0.875rem;
          font-family: inherit;
        }
        .form-group textarea {
          resize: vertical;
        }
        .form-divider {
          text-align: center;
          margin: 1.5rem 0;
          color: var(--text-secondary);
          font-size: 0.875rem;
        }
        .upload-area {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          padding: 1rem;
          border: 2px dashed var(--border);
          border-radius: 8px;
          margin-bottom: 1.5rem;
        }
        .upload-hint {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }
        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 0.75rem;
        }
      `}</style>
    </div>
  )
}
