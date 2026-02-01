import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { useApi } from '../hooks/useApi'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

interface ChatAreaProps {
  threadId: string | null
  onNewThread: () => void
  onUpdateTitle: (threadId: string, title: string) => void
}

export default function ChatArea({ threadId, onNewThread, onUpdateTitle }: ChatAreaProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { fetchApi } = useApi()

  useEffect(() => {
    if (threadId) {
      loadMessages()
    } else {
      setMessages([])
    }
  }, [threadId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadMessages = async () => {
    if (!threadId) return
    const data = await fetchApi<Message[]>(`/api/threads/${threadId}/messages`)
    if (data) {
      setMessages(data)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || sending) return

    const messageContent = input.trim()
    setInput('')
    setSending(true)

    // If no thread, create one first
    let targetThreadId = threadId
    if (!targetThreadId) {
      const newThread = await fetchApi<{ id: string }>('/api/threads', { method: 'POST' })
      if (!newThread) {
        setSending(false)
        return
      }
      targetThreadId = newThread.id
    }

    // Optimistically add user message
    const tempUserMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: messageContent,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempUserMessage])

    // Send to API
    const response = await fetchApi<{
      user_message: Message
      assistant_message: Message
    }>(`/api/threads/${targetThreadId}/messages`, {
      method: 'POST',
      body: { content: messageContent },
    })

    if (response) {
      // Replace temp message with real ones
      setMessages(prev => [
        ...prev.filter(m => m.id !== tempUserMessage.id),
        response.user_message,
        response.assistant_message,
      ])

      // Update thread title if this was the first message
      if (messages.length === 0) {
        const title = messageContent.slice(0, 50) + (messageContent.length > 50 ? '...' : '')
        onUpdateTitle(targetThreadId, title)
      }
    } else {
      // Remove optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== tempUserMessage.id))
    }

    setSending(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (!threadId && messages.length === 0) {
    return (
      <div className="chat-area">
        <div className="empty-state">
          <h2>Personal Agent</h2>
          <p>Start a new conversation or select an existing one</p>
          <button
            className="btn btn-primary"
            style={{ marginTop: '1rem' }}
            onClick={onNewThread}
          >
            Start New Chat
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="chat-area">
      <div className="messages-container">
        <div className="messages-list">
          {messages.map(message => (
            <div key={message.id} className="message">
              <div className={`message-role ${message.role}`}>
                {message.role === 'user' ? 'You' : 'Assistant'}
              </div>
              <div className="message-content">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            </div>
          ))}
          {sending && (
            <div className="message">
              <div className="message-role">Assistant</div>
              <div className="loading">
                <div className="spinner" />
                <span>Thinking...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            className="message-input"
            placeholder="Type a message..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={sending}
          />
          <button
            className="send-btn"
            onClick={sendMessage}
            disabled={!input.trim() || sending}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
