import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import { LabelsProvider } from './context/LabelsContext'
import Admin from './pages/Admin'
import Login from './pages/Login'
import User from './pages/User'
import { getRole } from './utils/auth'

function RootRedirect() {
  const role = getRole()
  if (role === 'admin') return <Navigate to="/admin" replace />
  if (role === 'user') return <Navigate to="/user" replace />
  return <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <LabelsProvider>
          <Routes>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/login" element={<Login />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="/user" element={<User />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </LabelsProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
