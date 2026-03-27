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
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm space-y-8">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand-50 border border-brand-200 text-3xl mb-1">
            🏷️
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">LabelForge</h1>
          <p className="text-gray-500 text-sm">PDF text label editor</p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white border border-gray-200 rounded-2xl p-6 space-y-5 shadow-sm"
        >
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600">Username</label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input-field"
              placeholder="Enter username"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600">Password</label>
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

          <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="text-center text-gray-400 text-xs pt-1">
            Demo: <code className="text-gray-500">admin / admin123</code> · <code className="text-gray-500">user / user123</code>
          </p>
        </form>
      </div>
    </div>
  )
}
