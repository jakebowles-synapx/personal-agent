import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

interface SidebarProps {
  threads: Thread[]
  currentThreadId: string | null
  onSelectThread: (id: string) => void
  onNewThread: () => void
  onDeleteThread: (id: string) => void
  onLoadThreads: () => void
  isOpen: boolean
  onClose: () => void
}

export default function Sidebar({
  threads,
  currentThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onLoadThreads,
  isOpen,
  onClose,
}: SidebarProps) {
  const location = useLocation()

  useEffect(() => {
    onLoadThreads()
  }, [onLoadThreads])

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <button className="new-chat-btn" onClick={onNewThread}>
          + New Chat
        </button>
      </div>

      <div className="thread-list">
        {threads.map(thread => (
          <div
            key={thread.id}
            className={`thread-item ${thread.id === currentThreadId && location.pathname === '/' ? 'active' : ''}`}
            onClick={() => onSelectThread(thread.id)}
          >
            <span className="thread-title">
              {thread.title || 'New conversation'}
            </span>
            <button
              className="thread-delete"
              onClick={(e) => {
                e.stopPropagation()
                onDeleteThread(thread.id)
              }}
              title="Delete thread"
            >
              &times;
            </button>
          </div>
        ))}
        {threads.length === 0 && (
          <div style={{ padding: '1rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            No conversations yet
          </div>
        )}
      </div>

      <nav className="sidebar-nav">
        <Link
          to="/memories"
          className={`nav-item ${location.pathname === '/memories' ? 'active' : ''}`}
          onClick={onClose}
        >
          <span>&#128218;</span>
          Memories
        </Link>
        <Link
          to="/settings"
          className={`nav-item ${location.pathname === '/settings' ? 'active' : ''}`}
          onClick={onClose}
        >
          <span>&#9881;</span>
          Settings
        </Link>
      </nav>
    </aside>
  )
}
