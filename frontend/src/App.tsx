import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { AdminShell, CompetitionPage, CompetitionsPage, EditionPage } from './admin'
import { LoginPage, RegisterPage } from './auth'
import { PublicEditionPage, MyQuizzesPage } from './public'
import { Home, JoinPage, PlayPage } from './participant'
import { Empty } from './components'

export default function App() {
  return <Routes><Route path="/" element={<Home/>}/><Route path="/login" element={<LoginPage/>}/><Route path="/register" element={<RegisterPage/>}/><Route path="/my-quizzes" element={<MyQuizzesPage/>}/><Route path="/editions/:id" element={<PublicEditionPage/>}/><Route path="/editions/:id/results" element={<PublicEditionPage results/>}/><Route path="/join/:id" element={<JoinPage/>}/><Route path="/play/:id" element={<PlayPage/>}/><Route path="/admin/login" element={<Navigate to="/login" replace/>}/><Route path="/admin" element={<AdminShell/>}><Route index element={<CompetitionsPage dashboard/>}/><Route path="competitions" element={<CompetitionsPage/>}/><Route path="competitions/:id" element={<CompetitionPage/>}/><Route path="editions/:id" element={<EditionPage/>}/></Route><Route path="*" element={<Empty title="Această pagină nu există."><Link to="/" className="button primary">Înapoi acasă</Link></Empty>}/></Routes>
}
