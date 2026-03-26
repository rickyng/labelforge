import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api'
import { useToast } from '../components/Toast'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { addToast } = useToast()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await login(username, password)
      addToast(`Welcome, ${res.username}!`, 'success')
      navigate(res.role === 'admin' ? '/admin' : '/user')
    } catch (err) {
      addToast(String(err), 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo / title */}
        <div className="text-center space-y-1">
          <div className="text-5xl">🏷️</div>
          <h1 className="text-2xl font-bold tracking-tight">LabelForge Web</h1>
          <p className="text-gray-500 text-sm">PDF text label editor</p>
        </div>

        {/* Login card */}
        <form
          onSubmit={handleSubmit}
          className="card space-y-4"
        >
          <h2 className="font-semibold text-gray-300">Sign in</h2>

          <div className="space-y-1">
            <label className="text-xs text-gray-500">Username</label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input-field"
              placeholder="admin or user"
              required
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-500">Password</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="text-center text-gray-600 text-xs">
            Demo credentials: <code className="text-gray-400">admin / admin123</code> ·{' '}
            <code className="text-gray-400">user / user123</code>
          </p>
        </form>
      </div>
    </div>
  )
}
