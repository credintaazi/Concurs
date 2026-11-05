import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowRight, Check, CheckCircle2, Clock3, LockKeyhole, BookOpen, Trophy, Users, Radio, ShieldCheck } from 'lucide-react'
import { api, ApiError } from './api'
import { AuthNav, useAuth } from './auth'
import { Brand, Connection, Empty, ErrorNotice, Loading, StatusBadge } from './components'
import { useEditionSocket } from './hooks'
import type { PublicEdition, QuizState, Results } from './types'

export function Home() {
  const auth = useAuth()
  useEditionSocket(0, !!auth.data?.user)
  const editions = useQuery({ queryKey: ['public-editions'], queryFn: () => api<PublicEdition[]>('/public/editions') })
  const [filter, setFilter] = useState('all')
  const visibleEditions = editions.data?.filter(e => filter === 'all' || (filter === 'open' ? e.status === 'WAITING' : filter === 'upcoming' ? e.status === 'SCHEDULED' : e.status === 'FINISHED'))
  return <div className="public-page">
    <header className="public-top"><Brand/><AuthNav/></header>
    <main className="home-main">
      <section className="home-hero" aria-labelledby="home-title">
      <div className="home-intro">
        <span className="eyebrow"><span className="live-dot"/> DESCOPERĂ BIBLIA, ÎMPREUNĂ</span>
        <h1 id="home-title">O întrebare bună.<br/>O bucurie <span>împărtășită.</span></h1>
        <p>Pune-ți cunoștințele biblice la încercare, alături de ceilalți. Fiecare întrebare este o ocazie să înveți ceva nou.</p>
        <div className="hero-actions"><a href="#concursuri" className="button primary">Descoperă concursurile<ArrowRight size={19}/></a><a href="#cum-participi" className="button secondary">Cum particip?</a></div>
        <div className="home-benefits"><span><ShieldCheck size={17}/>Puncte pentru corectitudine</span><span><Radio size={17}/>Împreună, în timp real</span></div>
      </div>
      <div className="hero-preview" aria-hidden="true"><span className="preview-shape shape-circle"/><span className="preview-shape shape-square"/><div className="preview-card"><div className="preview-heading"><span><BookOpen size={17}/> BIBLIA, PAS CU PAS</span><span className="preview-live">Împreună</span></div><div className="preview-book"><BookOpen size={52} strokeWidth={1.5}/></div><h2>Curiozitatea ne<br/>aduce împreună.</h2><p>Citește. Gândește. Descoperă.</p><div className="preview-answers"><span>A <i/></span><span>B <Check size={17}/></span><span>C <i/></span><span>D <i/></span></div><div className="preview-footer"><span><Users size={16}/> Un loc pentru fiecare</span><Trophy size={19}/></div></div><div className="preview-float"><span><CheckCircle2 size={22}/></span><div><strong>Fiecare răspuns contează.</strong><small>Înveți în ritmul concursului.</small></div></div></div>
      </section>
      <section id="concursuri" className="join-card" aria-labelledby="available-title">
        <div className="catalog-heading"><div><span className="eyebrow">ALEGE URMĂTOAREA PROVOCARE</span><h2 id="available-title">Ne vedem la concurs.</h2><p className="muted">Găsește ediția ta și intră cu parola primită de la organizator.</p></div><span className="catalog-count">{editions.data?.length ?? '—'} ediții publicate</span></div>
        <div className="filter-bar" role="group" aria-label="Filtrează edițiile">{[{id:'all',label:'Toate edițiile'},{id:'open',label:'Înscrieri deschise'},{id:'upcoming',label:'Programate'},{id:'finished',label:'Finalizate'}].map(f => <button key={f.id} className={filter === f.id ? 'active' : ''} aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>{f.label}</button>)}</div>
        {editions.isPending && <Loading/>}<ErrorNotice error={editions.error}/>
        <div className="public-edition-grid">{visibleEditions?.map((e,i) => <Link className={`public-edition edition-tone-${i%3}`} to={`/editions/${e.id}`} key={e.id}><div className="public-card-top"><span className="edition-book"><BookOpen size={24}/></span><StatusBadge status={e.status}/></div><small>{e.competition_title}</small><h3>{e.name}</h3><div className="edition-card-meta"><span><BookOpen size={15}/>{e.total_questions} întrebări</span><span><Users size={15}/>{e.participant_count} participanți</span></div><div className="edition-card-action"><span>{e.status === 'WAITING' ? 'Participă la concurs' : e.status === 'FINISHED' ? 'Vezi ediția' : 'Descoperă ediția'}</span><ArrowRight size={18}/></div></Link>)}</div>
        {editions.data && editions.data.length > 0 && visibleEditions?.length === 0 && <Empty title="Nicio ediție în această categorie."><p>Poți vedea celelalte concursuri în lista completă.</p><button className="button secondary" onClick={() => setFilter('all')}>Vezi toate edițiile</button></Empty>}
        {editions.data?.length === 0 && <div className="no-open"><span className="empty-calendar"><BookOpen size={29} strokeWidth={1.4}/></span><strong>Pregătim următoarea întâlnire.</strong><p>Edițiile vor apărea aici când sunt publicate. Ai deja o invitație? Deschide linkul primit de la organizator.</p><button className="button secondary compact" onClick={() => editions.refetch()}>Verifică din nou<ArrowRight size={15}/></button></div>}
        <div className="join-note"><LockKeyhole size={15}/><span>Te poți înscrie până la începerea concursului.</span></div>
      </section>
      <section id="cum-participi" className="participation-guide"><div className="guide-intro"><span className="eyebrow">SIMPLU, DE LA PRIMUL PAS</span><h2>Trei pași. Și ești în arenă.</h2><p className="muted">Tu aduci curiozitatea. Noi pregătim locul.</p></div><ol><li><span>01</span><BookOpen size={24}/><div><strong>Alege concursul</strong><p>Deschide ediția la care vrei să participi.</p></div></li><li><span>02</span><Users size={24}/><div><strong>Fă-ți loc în echipă</strong><p>Introdu numele tău și parola ediției.</p></div></li><li><span>03</span><Radio size={24}/><div><strong>Ne vedem la start</strong><p>Organizatorul dă ritmul. Toți văd aceeași întrebare.</p></div></li></ol></section>
    </main>
    <footer className="public-footer"><span>Quiz Arena</span><span>Fiecare întrebare contează.</span></footer>
  </div>
}

const joinSchema = z.object({ name: z.string().trim().min(2, 'Scrie un nume de minimum 2 caractere.').max(80), password: z.string().min(1, 'Introdu parola ediției.').max(128) })
export function JoinPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const edition = useQuery({ queryKey: ['public-edition', id], queryFn: () => api<PublicEdition>(`/public/editions/${id}`) })
  const existing = useQuery({ queryKey: ['edition', id, 'resume'], queryFn: () => api<QuizState>(`/editions/${id}/state`), retry: false })
  const form = useForm({ resolver: zodResolver(joinSchema), defaultValues: { name: '', password: '' } })
  const join = useMutation({ mutationFn: (v: z.infer<typeof joinSchema>) => api(`/editions/${id}/join`, 'POST', v), onSuccess: () => navigate(`/play/${id}`) })
  const closed = edition.data && edition.data.status !== 'WAITING'
  return <div className="auth-page"><header className="public-top"><Brand/><AuthNav/></header><main className="auth-card participant-auth">{edition.isPending ? <Loading/> : edition.error ? <ErrorNotice error={edition.error}/> : <><span className="eyebrow">{edition.data?.competition_title}</span><h1>{edition.data?.name}</h1><StatusBadge status={edition.data!.status}/>{existing.data?.participant ? <div className="resume-session"><h3>Bine ai revenit, {existing.data.participant.name}!</h3><p>Sesiunea ta este salvată. Poți reveni în concurs.</p><Link className="button primary" to={`/play/${id}`}>Continuă concursul<ArrowRight size={18}/></Link></div> : closed ? <div className="closed-notice"><LockKeyhole size={28}/><h3>{['DRAFT', 'SCHEDULED'].includes(edition.data?.status ?? '') ? 'Înscrierile nu sunt încă deschise.' : 'Concursul a început deja.'}</h3><p>{['DRAFT', 'SCHEDULED'].includes(edition.data?.status ?? '') ? 'Așteaptă invitația organizatorului.' : 'Nu mai sunt permise înscrieri. Participanții înscriși pot reveni folosind browserul în care au intrat.'}</p></div> : <><p className="muted">Intră în camera de așteptare. Organizatorul va da startul când toată lumea este pregătită.</p><form className="form" onSubmit={form.handleSubmit(v => join.mutate(v))}><label>Numele tău<input {...form.register('name')} autoComplete="name" placeholder="Cum te numești?"/></label><small className="field-error">{form.formState.errors.name?.message}</small><label>Parola ediției<input {...form.register('password')} type="password" autoComplete="off" placeholder="Parola primită de la organizator"/></label><small className="field-error">{form.formState.errors.password?.message}</small><ErrorNotice error={join.error}/><button className="button primary" disabled={join.isPending || existing.isPending}>{join.isPending ? 'Se verifică…' : 'Intră în concurs'}<ArrowRight size={18}/></button></form><div className="join-note"><LockKeyhole size={14}/>Fără cont. Numele tău este unic în această ediție.</div></>}</>}</main><footer className="public-footer">Quiz Arena · Fiecare întrebare contează.</footer></div>
}

export function PlayPage() {
  const id = Number(useParams().id)
  const state = useQuery({ queryKey: ['edition', id, 'state'], queryFn: () => api<QuizState>(`/editions/${id}/state`) })
  const connection = useEditionSocket(id)
  const s = state.data
  return <div className="play-page"><header className="public-top"><Brand/><div className="play-nav"><Connection value={connection}/><AuthNav/></div></header><main className={`play-main ${s?.status === 'FINISHED' ? 'wide' : ''}`}>{state.isPending ? <Loading/> : state.error instanceof ApiError && state.error.status === 401 ? <div className="auth-card"><h2>Intră în ediție pentru a continua.</h2><p className="muted">Sesiunea lipsește sau a expirat.</p><Link to={`/join/${id}`} className="button primary">Pagina de participare<ArrowRight size={17}/></Link></div> : state.error ? <><ErrorNotice error={state.error}/><button className="button secondary" onClick={() => state.refetch()}>Reîncearcă</button></> : s && !s.participant ? <Empty title="Acesta este spațiul participanților."><Link to={`/join/${id}`} className="button primary">Intră cu numele tău</Link></Empty> : s && <><div className="play-heading"><span className="eyebrow">{s.competition_title}</span><h2>{s.name}</h2><span className="participant-chip"><span className="mini-avatar">{s.participant?.name[0].toUpperCase()}</span>{s.participant?.name}</span></div>{s.status === 'WAITING' && <section className="waiting-card"><div className="waiting-orbit"><div className="pulse-ring"/><Clock3 size={47}/><i/><i/><i/></div><span className="eyebrow">EȘTI ÎN LOCUL POTRIVIT</span><h1>Salut, {s.participant?.name}!</h1><p>Totul e pregătit. Așteaptă ca organizatorul<br/>să dea startul concursului.</p><div className="waiting-count"><Users size={21}/><strong>{s.participant_count}</strong><span>participanți înscriși</span></div><div className="waiting-info"><span className="live-dot"/>Prima întrebare va apărea automat.</div></section>}{['LIVE', 'PAUSED'].includes(s.status) && s.question && <AnswerCard key={s.question.id} state={s} connected={connection === 'connected'}/ >}{s.status === 'FINISHED' && <ResultsView editionId={id} participantId={s.participant?.id}/>}</>}</main><footer className="public-footer">Quiz Arena · Învățăm. Participăm. Creștem.</footer></div>
}

export function AnswerCard({ state, connected }: { state: QuizState; connected: boolean }) {
  const q = state.question!
  const [selected, setSelected] = useState<number[]>(state.selected_option_ids ?? [])
  const client = useQueryClient()
  const submit = useMutation({ mutationFn: () => api(`/editions/${state.id}/answers`, 'POST', { question_id: q.id, option_ids: selected }), onSettled: () => client.invalidateQueries({ queryKey: ['edition', state.id] }) })
  const answered = state.answered || submit.isSuccess
  const choices = state.answered ? state.selected_option_ids ?? [] : selected
  return <section className="answer-card"><div className="quiz-session-state"><Clock3 size={14}/>{state.status === 'PAUSED' ? 'Concursul este pus pe pauz\u0103' : 'Tu te concentrezi. Organizatorul d\u0103 ritmul.'}</div>{state.status === 'PAUSED' && <div className="paused-banner"><Clock3 size={24}/><div><strong>Concursul este în pauză</strong><p>Răspunsurile sunt temporar blocate. Organizatorul va relua concursul.</p></div></div>}<div className="progress-label">Întrebarea {state.current_index + 1} din {state.total_questions}<span>{q.type === 'SINGLE_CHOICE' ? 'Răspuns unic' : 'Răspuns multiplu'}</span></div><progress aria-label="Progresul concursului" max={state.total_questions} value={state.current_index + 1}/><h1>{q.text}</h1><p className="muted small">{q.type === 'SINGLE_CHOICE' ? 'Alege o singură variantă.' : 'Selectează toate variantele pe care le consideri corecte.'}</p><fieldset className="answer-options" disabled={answered || submit.isPending || !connected || state.status === 'PAUSED'}><legend className="sr-only">Variante de răspuns</legend>{q.options.map((o, i) => <label key={o.id} className={`answer-option ${choices.includes(o.id) ? 'selected' : ''}`}><input type={q.type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'} name={`question-${q.id}`} checked={choices.includes(o.id)} onChange={() => setSelected(previous => q.type === 'SINGLE_CHOICE' ? [o.id] : previous.includes(o.id) ? previous.filter(x => x !== o.id) : [...previous, o.id])}/><span className="option-letter">{String.fromCharCode(65 + i)}</span><span>{o.text}</span><span className="selection-indicator">{choices.includes(o.id) && <Check size={15}/>}</span></label>)}</fieldset><ErrorNotice error={submit.error}/>{answered ? <div className="answer-confirmation" role="status"><CheckCircle2 size={23}/><div><strong>Răspuns înregistrat!</strong><p>Așteaptă următoarea întrebare. Organizatorul dă ritmul.</p></div></div> : <><button className="button primary full" disabled={!choices.length || submit.isPending || !connected || state.status === 'PAUSED'} onClick={() => submit.mutate()}>{submit.isPending ? 'Se trimite…' : 'Trimite răspunsul'}<ArrowRight size={18}/></button><p className="hint centered">Răspunsul este final după trimitere. Viteza nu influențează punctajul.</p></>}</section>
}

export function ResultsView({ editionId, participantId }: { editionId: number; participantId?: number }) {
  const results = useQuery({ queryKey: ['edition', editionId, 'results'], queryFn: () => api<Results>(`/editions/${editionId}/results`) })
  if (results.isPending) return <Loading/>
  if (!results.data) return <ErrorNotice error={results.error}/>
  const r = results.data
  return <div className="results-view"><section className="results-hero"><Trophy size={44}/><span className="eyebrow">CONCURS FINALIZAT</span><h1>Felicitări pentru participare!</h1><p>Fiecare întrebare a fost un pas înainte.</p>{r.your_score !== null && <div className="your-score"><strong>{r.your_score}<span> / {r.edition.total_questions}</span></strong><small>PUNCTAJUL TĂU</small></div>}</section><section className="panel"><div className="section-heading"><h2><Trophy size={20}/>Clasamentul final</h2><span className="muted small">{r.leaderboard.length} participanți</span></div><div className="leaderboard"><div className="leaderboard-head"><span>LOC</span><span>PARTICIPANT</span><span>PUNCTE</span></div>{r.leaderboard.map(row => <div className={`leaderboard-row ${row.participant_id === participantId ? 'is-you' : ''}`} key={row.participant_id}><strong className={`rank rank-${row.rank}`}>{row.rank <= 3 ? <Trophy size={17}/> : null}{row.rank}</strong><strong>{row.name}{row.participant_id === participantId && <small> TU</small>}</strong><span>{row.score}<small> / {r.edition.total_questions}</small></span></div>)}</div>{!r.leaderboard.length && <p className="muted">Nu au fost înscriși participanți.</p>}<p className="hint">Scor egal, același rang. 1 punct pentru fiecare răspuns complet corect.</p></section><section className="review-section"><div className="section-heading"><h2>Întrebări și răspunsuri corecte</h2></div>{r.questions.map((q, i) => {
    const answer = r.your_answers.find(a => a.question_id === q.id)
    return <article key={q.id} className="question-card review-card"><div className="question-heading"><span className="question-number">{String(i + 1).padStart(2, '0')}</span><h3>{q.text}</h3>{participantId && <span className={`review-score ${answer?.points ? 'correct' : ''}`}>{answer?.points ? '+1 punct' : answer ? '0 puncte' : 'Fără răspuns'}</span>}</div>{q.options.map(o => <div key={o.id} className={`review-option ${o.is_correct ? 'correct' : answer?.option_ids.includes(o.id) ? 'incorrect' : ''}`}><span>{o.is_correct ? <CheckCircle2 size={17}/> : <span className="review-empty"/>}</span><span>{o.text}</span>{answer?.option_ids.includes(o.id) && <small>Răspunsul tău</small>}{o.is_correct && <small>Corect</small>}</div>)}</article>
  })}</section></div>
}
