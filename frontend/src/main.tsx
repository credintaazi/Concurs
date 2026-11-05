import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from './api'
import App from './App'
import './styles.css'
import './design-system.css'

const client = new QueryClient({ defaultOptions: { queries: {
  retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  refetchOnWindowFocus: true, staleTime: 10000,
} } })

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><BrowserRouter><App/></BrowserRouter></QueryClientProvider></React.StrictMode>)
