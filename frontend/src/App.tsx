import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import { LabelsProvider } from './context/LabelsContext'
import Editor from './pages/Editor'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <LabelsProvider>
          <Routes>
            <Route path="/" element={<Editor />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </LabelsProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
