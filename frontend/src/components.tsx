import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowLeft, BookOpen, LoaderCircle, Radio, Sparkles, X } from 'lucide-react'
import type { Status } from './types'

export function Brand() {
  return <Link to="/" className="brand" aria-label="Quiz Arena — acasă"><span className="brand-mark"><BookOpen size={23} strokeWidth={1.6}/></span><span>quiz<span className="brand-light">arena</span><small>FIECARE ÎNTREBARE CONTEAZĂ</small></span></Link>
}
const statusText: Record<Status, string> = { DRAFT: 'În pregătire', SCHEDULED: 'Programat', WAITING: 'Înscrieri deschise', LIVE: 'În desfășurare', PAUSED: 'În pauză', FINISHED: 'Finalizat' }
export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge status-${status}`}><i/>{statusText[status]}</span>
}
export function Connection({ value }: { value: string }) {
  return <span className={`connection ${value}`} role="status"><Radio size={14}/>{value === 'connected' ? 'Conectat în timp real' : value === 'connecting' ? 'Se conectează…' : 'Conexiune pierdută · reconectare…'}</span>
}
export function ErrorNotice({ error }: { error?: unknown }) {
  return error ? <div className="error-notice" role="alert"><AlertCircle size={18}/><span>{error instanceof Error ? error.message : 'A apărut o eroare. Încearcă din nou.'}</span></div> : null
}
export function Loading() { return <div className="loading" role="status"><LoaderCircle className="spin"/> Se încarcă…</div> }
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><Sparkles size={30}/><h3>{title}</h3>{children}</div>
}
export function Back({ to, children }: { to: string; children: ReactNode }) {
  return <Link className="back" to={to}><ArrowLeft size={16}/>{children}</Link>
}
export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input, textarea, select, a[href], [tabindex="0"]') ?? [])
    focusable()[0]?.focus()
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current()
      if (event.key === 'Tab') {
        const elements = focusable()
        if (!elements.length) return
        if (event.shiftKey && document.activeElement === elements[0]) { event.preventDefault(); elements.at(-1)?.focus() }
        else if (!event.shiftKey && document.activeElement === elements.at(-1)) { event.preventDefault(); elements[0]?.focus() }
      }
    }
    document.addEventListener('keydown', key)
    return () => { document.body.style.overflow = overflow; document.removeEventListener('keydown', key); previous?.focus() }
  }, [])
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><div ref={dialog} className="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div className="modal-head"><h2 id="dialog-title">{title}</h2><button className="icon-button" aria-label="Închide" onClick={onClose}><X size={20}/></button></div>{children}</div></div>
}
export function Confirm({ title, description, onConfirm, onClose, pending, error, label = 'Șterge definitiv' }: {
  title: string; description: string; onConfirm: () => void; onClose: () => void; pending: boolean; error?: unknown; label?: string
}) {
  return <Modal title={title} onClose={pending ? () => {} : onClose}><p className="muted">{description}</p><ErrorNotice error={error}/><div className="form-actions"><button className="button secondary" disabled={pending} onClick={onClose}>Renunță</button><button className="button danger" disabled={pending} onClick={onConfirm}>{pending ? 'Se procesează…' : label}</button></div></Modal>
}
