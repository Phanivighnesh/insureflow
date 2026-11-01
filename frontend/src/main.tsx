import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import { ToastProvider } from './components/ui'
import { ApiError } from './api/client'
import './index.css'

export const makeQueryClient = () => new QueryClient({ defaultOptions: { queries: {
  staleTime: 5000, refetchOnWindowFocus: false,
  retry: (n, e) => !(e instanceof ApiError && e.status >= 400 && e.status < 500) && n < 2 } } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={makeQueryClient()}><BrowserRouter><AuthProvider><ToastProvider><App /></ToastProvider></AuthProvider></BrowserRouter></QueryClientProvider></React.StrictMode>)
