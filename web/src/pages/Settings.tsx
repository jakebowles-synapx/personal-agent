import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useApi'

interface HarvestStatus {
  configured: boolean
  connected: boolean
  company_name: string | null
  error: string | null
}

export default function Settings() {
  const [msConnected, setMsConnected] = useState(false)
  const [harvestStatus, setHarvestStatus] = useState<HarvestStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const { fetchApi } = useApi()

  useEffect(() => {
    checkStatus()
  }, [])

  const checkStatus = async () => {
    setLoading(true)
    const [msData, harvestData] = await Promise.all([
      fetchApi<{ connected: boolean }>('/api/microsoft/status'),
      fetchApi<HarvestStatus>('/api/harvest/status'),
    ])
    if (msData) {
      setMsConnected(msData.connected)
    }
    if (harvestData) {
      setHarvestStatus(harvestData)
    }
    setLoading(false)
  }

  const connectMicrosoft = async () => {
    const data = await fetchApi<{ url: string }>('/api/microsoft/auth-url')
    if (data) {
      // Open OAuth flow in new window
      const authWindow = window.open(data.url, 'ms-auth', 'width=600,height=700')

      // Poll for window close
      const checkClosed = setInterval(() => {
        if (authWindow?.closed) {
          clearInterval(checkClosed)
          checkStatus()
        }
      }, 500)
    }
  }

  const disconnectMicrosoft = async () => {
    if (!confirm('Disconnect your Microsoft 365 account?')) {
      return
    }
    await fetchApi('/api/microsoft/disconnect', { method: 'POST' })
    setMsConnected(false)
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      <div className="settings-section">
        <h3>Microsoft 365</h3>
        {loading ? (
          <div className="loading">
            <div className="spinner" />
            <span>Checking status...</span>
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: '1rem' }}>
              <span
                className={`status-badge ${msConnected ? 'connected' : 'disconnected'}`}
              >
                <span>{msConnected ? '●' : '○'}</span>
                {msConnected ? 'Connected' : 'Not connected'}
              </span>
            </div>

            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              {msConnected
                ? 'Your Microsoft 365 account is connected. You can access your calendar, emails, Teams messages, and files.'
                : 'Connect your Microsoft 365 account to access your calendar, emails, Teams messages, and files.'}
            </p>

            {msConnected ? (
              <button className="btn btn-outline" onClick={disconnectMicrosoft}>
                Disconnect
              </button>
            ) : (
              <button className="btn btn-primary" onClick={connectMicrosoft}>
                Connect Microsoft 365
              </button>
            )}
          </div>
        )}
      </div>

      <div className="settings-section">
        <h3>Harvest Time Tracking</h3>
        {loading ? (
          <div className="loading">
            <div className="spinner" />
            <span>Checking status...</span>
          </div>
        ) : harvestStatus ? (
          <div>
            <div style={{ marginBottom: '1rem' }}>
              <span
                className={`status-badge ${harvestStatus.connected ? 'connected' : 'disconnected'}`}
              >
                <span>{harvestStatus.connected ? '●' : '○'}</span>
                {harvestStatus.connected
                  ? `Connected${harvestStatus.company_name ? ` - ${harvestStatus.company_name}` : ''}`
                  : harvestStatus.configured
                  ? 'Connection failed'
                  : 'Not configured'}
              </span>
            </div>

            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              {harvestStatus.connected
                ? 'Harvest is connected. You can track time, view time entries, and manage projects.'
                : harvestStatus.error || 'Configure Harvest by setting HARVEST_ACCOUNT_ID and HARVEST_ACCESS_TOKEN in your environment.'}
            </p>
          </div>
        ) : null}
      </div>

      <div className="settings-section">
        <h3>About</h3>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Personal Agent v0.1.0
        </p>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
          An AI assistant with long-term memory and Microsoft 365 integration.
        </p>
      </div>
    </div>
  )
}
