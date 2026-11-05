import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowRight, LogOut, ShieldCheck, UserRound } from 'lucide-react'
import { api } from './api'
import { Brand, ErrorNotice, Loading } from './components'
import type { AccountSession } from './types'

export function useAuth() {
  return useQuery({ queryKey: ['auth-session'], queryFn: () => api<AccountSession>('/auth/session'), retry: false })
}

export function useLogout() {
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({ mutationFn: () => api('/auth/logout', 'POST'), onSuccess: () => {
    client.clear()
    navigate('/')
  } })
}

export function AuthNav() {
  const auth = useAuth()
  const logout = useLogout()
  if (auth.isPending) return <span className="hint" role="status">Se verifică sesiunea…</span>
  if (auth.error) return <div><ErrorNotice error={auth.error}/><button className="text-link" onClick={() => auth.refetch()}>Reîncearcă</button></div>
  const user = auth.data?.user
  return <div className="account-nav">{user ? <><span className="account-name"><UserRound size={15}/><span>{user.name}<small>{user.role === 'ADMIN' ? 'Administrator' : 'Participant'}</small></span></span>{user.role === 'ADMIN' ? <Link className="button secondary compact" to="/admin"><ShieldCheck size={15}/>Dashboard</Link> : <Link className="button secondary compact" to="/my-quizzes">Participările mele</Link>}<button className="icon-button" aria-label="Deconectare" disabled={logout.isPending} onClick={() => logout.mutate()}><LogOut size={17}/></button></> : <><Link className="text-link" to="/login">Autentificare</Link><Link className="button primary compact" to="/register">Creează cont</Link></>}<ErrorNotice error={logout.error}/></div>
}

const loginSchema = z.object({ email: z.email('Introdu o adresă de email validă.').max(254), password: z.string().min(1, 'Introdu parola.').max(128) })
const registerSchema = loginSchema.extend({ name: z.string().trim().min(2, 'Numele trebuie să aibă minimum 2 caractere.').max(80), password: z.string().min(12, 'Parola trebuie să aibă minimum 12 caractere.').max(128), confirm: z.string() }).refine(v => v.password === v.confirm, { path: ['confirm'], message: 'Parolele nu coincid.' })

function destination(params: URLSearchParams, isAdmin: boolean) {
  const target = params.get('returnTo')
  if (target?.startsWith('/') && !target.startsWith('//') && !target.startsWith('/login') && !target.startsWith('/register')) return target
  return isAdmin ? '/admin' : '/'
}

export function LoginPage() {
  const auth = useAuth()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const form = useForm({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } })
  const login = useMutation({ mutationFn: (v: z.infer<typeof loginSchema>) => api<AccountSession>('/auth/login', 'POST', v), onSuccess: result => {
    client.clear()
    client.setQueryData(['auth-session'], result)
    navigate(destination(params, result.user?.role === 'ADMIN'))
  } })
  if (auth.isPending) return <Loading/>
  if (auth.data?.user) return <Navigate replace to={destination(params, auth.data.user.role === 'ADMIN')}/>
  return <div className="auth-page"><header className="public-top"><Brand/><Link to="/" className="text-link">Înapoi la concursuri<ArrowRight size={16}/></Link></header><main className="auth-card"><span className="eyebrow"><ShieldCheck size={15}/>CONTUL TĂU QUIZ ARENA</span><h1>Bine ai revenit.</h1><p className="muted">Autentifică-te pentru a-ți păstra participările și a reveni la concurs de pe orice dispozitiv.</p><form className="form" onSubmit={form.handleSubmit(v => login.mutate(v))}><label>Email<input type="email" {...form.register('email')} autoComplete="email" placeholder="nume@exemplu.ro"/></label><small className="field-error">{form.formState.errors.email?.message}</small><label>Parolă<input type="password" {...form.register('password')} autoComplete="current-password"/></label><small className="field-error">{form.formState.errors.password?.message}</small><ErrorNotice error={login.error}/><button className="button primary" disabled={login.isPending}>{login.isPending ? 'Se verifică…' : 'Autentifică-te'}<ArrowRight size={17}/></button></form><p className="auth-switch">Nu ai cont? <Link to={`/register${params.size ? `?${params}` : ''}`}>Creează un cont</Link></p><p className="hint">Participarea cu nume și parola ediției rămâne disponibilă și fără cont.</p></main><footer className="public-footer">Quiz Arena · Corectitudinea contează. Viteza nu aduce puncte.</footer></div>
}

export function RegisterPage() {
  const auth = useAuth()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const form = useForm({ resolver: zodResolver(registerSchema), defaultValues: { name: '', email: '', password: '', confirm: '' } })
  const register = useMutation({ mutationFn: (v: z.infer<typeof registerSchema>) => api<AccountSession>('/auth/register', 'POST', { name: v.name, email: v.email, password: v.password }), onSuccess: result => {
    client.clear()
    client.setQueryData(['auth-session'], result)
    navigate(destination(params, false))
  } })
  if (auth.isPending) return <Loading/>
  if (auth.data?.user) return <Navigate replace to={destination(params, auth.data.user.role === 'ADMIN')}/>
  return <div className="auth-page"><header className="public-top"><Brand/><Link className="text-link" to="/login">Am deja cont<ArrowRight size={16}/></Link></header><main className="auth-card"><span className="eyebrow"><UserRound size={15}/>PRIMUL PAS ÎN ARENĂ</span><h1>Creează-ți contul.</h1><p className="muted">Un singur cont pentru toate concursurile tale.</p><form className="form" onSubmit={form.handleSubmit(v => register.mutate(v))}><label>Numele tău<input {...form.register('name')} autoComplete="name"/></label><small className="field-error">{form.formState.errors.name?.message}</small><label>Email<input type="email" {...form.register('email')} autoComplete="email"/></label><small className="field-error">{form.formState.errors.email?.message}</small><label>Parolă<input type="password" {...form.register('password')} autoComplete="new-password" placeholder="Minimum 12 caractere"/></label><small className="field-error">{form.formState.errors.password?.message}</small><label>Confirmă parola<input type="password" {...form.register('confirm')} autoComplete="new-password"/></label><small className="field-error">{form.formState.errors.confirm?.message}</small><ErrorNotice error={register.error}/><button className="button primary" disabled={register.isPending}>{register.isPending ? 'Se creează contul…' : 'Creează contul'}<ArrowRight size={17}/></button></form><p className="auth-switch">Ai deja cont? <Link to={`/login${params.size ? `?${params}` : ''}`}>Autentifică-te</Link></p></main><footer className="public-footer">Quiz Arena · Învățăm. Participăm. Creștem.</footer></div>
}
