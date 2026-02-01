import { useState, useCallback } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import Dashboard from './pages/Dashboard'
import Recommendations from './pages/Recommendations'
import Knowledge from './pages/Knowledge'
import Agents from './pages/Agents'
import Memories from './pages/Memories'
import Settings from './pages/Settings'
import { useApi } from './hooks/useApi'

interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

function App() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { fetchApi } = useApi()
  const navigate = useNavigate()

  const loadThreads = useCallback(async () => {
    const data = await fetchApi<Thread[]>('/api/threads')
    if (data) {
      setThreads(data)
    }
  }, [fetchApi])

  const createThread = async () => {
    const data = await fetchApi<Thread>('/api/threads', { method: 'POST' })
    if (data) {
      setThreads(prev => [data, ...prev])
      setCurrentThreadId(data.id)
      navigate('/')
      setSidebarOpen(false)
    }
  }

  const selectThread = (threadId: string) => {
    setCurrentThreadId(threadId)
    navigate('/')
    setSidebarOpen(false)
  }

  const deleteThread = async (threadId: string) => {
    await fetchApi(`/api/threads/${threadId}`, { method: 'DELETE' })
    setThreads(prev => prev.filter(t => t.id !== threadId))
    if (currentThreadId === threadId) {
      setCurrentThreadId(null)
    }
  }

  const updateThreadTitle = (threadId: string, title: string) => {
    setThreads(prev => prev.map(t =>
      t.id === threadId ? { ...t, title } : t
    ))
  }

  return (
    <div className="app-layout">
      <Sidebar
        threads={threads}
        currentThreadId={currentThreadId}
        onSelectThread={selectThread}
        onNewThread={createThread}
        onDeleteThread={deleteThread}
        onLoadThreads={loadThreads}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />

      <main className="main-content">
        <div className="mobile-header">
          <button className="menu-btn" onClick={() => setSidebarOpen(true)}>
            &#9776;
          </button>
          <span style={{ marginLeft: '1rem', fontWeight: 500 }}>Personal Agent</span>
        </div>

        <Routes>
          <Route
            path="/"
            element={
              <ChatArea
                threadId={currentThreadId}
                onNewThread={createThread}
                onUpdateTitle={updateThreadTitle}
              />
            }
          />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/memories" element={<Memories />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
