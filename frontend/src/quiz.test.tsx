import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, it, expect } from 'vitest'
import { AnswerCard } from './participant'
import { QuestionForm } from './forms'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { AdminShell } from './admin'
import { AuthNav } from './auth'
import type { QuizState } from './types'

const state = { id: 1, current_index: 0, total_questions: 2, answered: false,
  question: { id: 4, text: 'Care este răspunsul?', type: 'SINGLE_CHOICE', position: 0, options: [{ id: 1, text: 'Prima variantă' }, { id: 2, text: 'A doua variantă' }] },
} as QuizState
const wrap = (value: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{value}</QueryClientProvider>)

describe('Participant answer flow', () => {
  it('requires a selection, submits once and confirms without revealing the key', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ accepted: true }) })
    vi.stubGlobal('fetch', fetch)
    wrap(<AnswerCard state={state} connected/>)
    expect(screen.getByRole('button', { name: /Trimite răspunsul/ })).toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: /Prima variantă/ }))
    await userEvent.click(screen.getByRole('button', { name: /Trimite răspunsul/ }))
    expect(await screen.findByText('Răspuns înregistrat!')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('radio', { name: /Prima variantă/ })).toBeDisabled()
    vi.unstubAllGlobals()
  })
  it('restores an already submitted answer after refresh', () => {
    wrap(<AnswerCard state={{ ...state, answered: true, selected_option_ids: [2] }} connected/>)
    expect(screen.getByRole('radio', { name: /A doua variantă/ })).toBeChecked()
    expect(screen.queryByRole('button', { name: /Trimite/ })).not.toBeInTheDocument()
  })
  it('prevents sending while disconnected', () => {
    wrap(<AnswerCard state={state} connected={false}/>)
    expect(screen.getByRole('radio', { name: /Prima variantă/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Trimite/ })).toBeDisabled()
  })
  it('blocks answers during pause and preserves an unsent selection on resume', async () => {
    const client = new QueryClient()
    const ui = (status: QuizState['status']) => <QueryClientProvider client={client}><AnswerCard state={{ ...state, status }} connected/></QueryClientProvider>
    const view = render(ui('LIVE'))
    await userEvent.click(screen.getByRole('radio', { name: /Prima variantă/ }))
    view.rerender(ui('PAUSED'))
    expect(screen.getByText('Concursul este în pauză')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Prima variantă/ })).toBeChecked()
    expect(screen.getByRole('button', { name: /Trimite/ })).toBeDisabled()
    view.rerender(ui('LIVE'))
    expect(screen.getByRole('radio', { name: /Prima variantă/ })).toBeChecked()
    expect(screen.getByRole('button', { name: /Trimite/ })).toBeEnabled()
  })
})

describe('Frontend account roles', () => {
  it('blocks the admin route for USER accounts before mounting administrative pages', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ user: { id: 1, email: 'user@example.com', name: 'Participant', role: 'USER' }, csrf: 'test-csrf' }) }))
    const client = new QueryClient()
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/admin']}><Routes><Route path="/admin" element={<AdminShell/>}><Route index element={<div>SECRET ADMIN CONTENT<Outlet/></div>}/></Route></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('Acces rezervat administratorilor.')).toBeInTheDocument()
    expect(screen.queryByText('SECRET ADMIN CONTENT')).not.toBeInTheDocument()
    vi.unstubAllGlobals()
  })
  it('only shows dashboard navigation for ADMIN accounts', async () => {
    const client = new QueryClient()
    client.setQueryData(['auth-session'], { user: { id: 1, email: 'admin@example.com', name: 'Admin', role: 'ADMIN' }, csrf: 'test-csrf' })
    // Keep the cached session fresh so this test only checks navigation by role.
    client.setQueryDefaults(['auth-session'], { staleTime: Infinity })
    render(<QueryClientProvider client={client}><MemoryRouter><AuthNav/></MemoryRouter></QueryClientProvider>)
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Participările mele' })).not.toBeInTheDocument()
  })
})

describe('Question authoring', () => {
  it('rejects multiple-choice with only one correct option', async () => {
    const save = vi.fn()
    render(<QuestionForm pending={false} save={save}/>)
    fireEvent.change(screen.getByLabelText('Întrebarea'), { target: { value: 'Întrebare validă?' } })
    fireEvent.change(screen.getByLabelText('Tipul răspunsului'), { target: { value: 'MULTIPLE_CHOICE' } })
    for (let i = 1; i <= 4; i++) fireEvent.change(screen.getByLabelText(`Text varianta ${i}`), { target: { value: `Răspuns ${i}` } })
    fireEvent.click(screen.getByLabelText('Varianta 1 corectă'))
    fireEvent.click(screen.getByRole('button', { name: 'Salvează întrebarea' }))
    expect(await screen.findByText('Marchează cel puțin două variante corecte.')).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
    fireEvent.click(screen.getByLabelText('Varianta 2 corectă'))
    fireEvent.click(screen.getByRole('button', { name: 'Salvează întrebarea' }))
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1))
  })
})
