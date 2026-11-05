import { useQuery } from '@tanstack/react-query'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowRight, BookOpen, CalendarDays, Users } from 'lucide-react'
import { api } from './api'
import { AuthNav, useAuth } from './auth'
import { Back, Brand, Connection, Empty, ErrorNotice, Loading, StatusBadge } from './components'
import { useEditionSocket } from './hooks'
import { ResultsView } from './participant'
import type { PublicEdition } from './types'

export function PublicEditionPage({ results = false }: { results?: boolean }) {
  const id = Number(useParams().id)
  const auth = useAuth()
  const connection = useEditionSocket(0, !!auth.data?.user)
  const edition = useQuery({ queryKey: ['public-edition', id], queryFn: () => api<PublicEdition>(`/public/editions/${id}`) })
  return <div className="public-page"><header className="public-top"><Brand/><AuthNav/></header><main className="public-detail"><Back to="/">Toate concursurile</Back>{edition.isPending ? <Loading/> : edition.error ? <ErrorNotice error={edition.error}/> : edition.data && <><div className="panel"><div className="section-heading"><span className="eyebrow">{edition.data.competition_title}</span><StatusBadge status={edition.data.status}/></div><h1>{edition.data.name}</h1><p className="muted description-text">{edition.data.description || 'Un concurs în care cunoștințele contează.'}</p><div className="edition-summary"><span><BookOpen size={16}/>{edition.data.total_questions} întrebări</span><span><Users size={16}/>{edition.data.participant_count} participanți</span>{auth.data?.user && <Connection value={connection}/>}</div>{edition.data.scheduled_at && <p className="scheduled-info"><CalendarDays size={17}/>Programat pentru {new Date(edition.data.scheduled_at).toLocaleString('ro-RO')}</p>}<div className="scoring-note">1 răspuns complet corect = 1 punct. Fără bonus de viteză. Scorurile egale au același rang.</div><div className="button-group detail-actions">{edition.data.status === 'WAITING' && <Link className="button primary" to={`/join/${id}`}>Intră în concurs<ArrowRight size={17}/></Link>}{['LIVE', 'PAUSED'].includes(edition.data.status) && <><p className="muted small">Înscrierile sunt închise. Participanții înscriși pot reveni la sesiunea lor.</p><Link className="button secondary" to={`/play/${id}`}>Revino în concurs</Link></>}{edition.data.status === 'SCHEDULED' && <p className="muted small">Organizatorul va deschide înscrierile înainte de start.</p>}{edition.data.results_published && <Link className="button primary" to={auth.data?.user ? `/editions/${id}/results` : `/login?returnTo=${encodeURIComponent(`/editions/${id}/results`)}`}>Vezi rezultatele</Link>}</div></div>{results && (auth.isPending ? <Loading/> : auth.data?.user ? <ResultsView editionId={id}/> : <Navigate to={`/login?returnTo=${encodeURIComponent(`/editions/${id}/results`)}`} replace/>)}</>}</main><footer className="public-footer">Quiz Arena · Corectitudinea contează, nu viteza.</footer></div>
}

export function MyQuizzesPage() {
  const auth = useAuth()
  useEditionSocket(0, !!auth.data?.user)
  const entries = useQuery({ queryKey: ['participations'], queryFn: () => api<PublicEdition[]>('/auth/participations'), enabled: !!auth.data?.user })
  if (auth.isPending) return <Loading/>
  if (!auth.data?.user) return <Navigate to="/login?returnTo=/my-quizzes" replace/>
  return <div className="public-page"><header className="public-top"><Brand/><AuthNav/></header><main className="public-detail"><Back to="/">Toate concursurile</Back><h1>Participările mele</h1><p className="muted description-text">Sesiunile asociate contului tău. Poți reveni și după START.</p><ErrorNotice error={entries.error}/>{entries.isPending && <Loading/>}<div className="edition-list">{entries.data?.map(e => <Link className="edition-row" key={e.id} to={e.is_active ? `/play/${e.id}` : `/editions/${e.id}`}><div className="grow"><h3>{e.name}</h3><p>{e.competition_title} · {e.participant_name}{!e.is_active && ' · Participare închisă'}</p></div><StatusBadge status={e.status}/><ArrowRight size={17}/></Link>)}</div>{entries.data?.length === 0 && <Empty title="Primul concurs te așteaptă."><Link className="button primary" to="/">Descoperă concursurile</Link></Empty>}</main></div>
}
