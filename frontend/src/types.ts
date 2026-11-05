export type Status = 'DRAFT' | 'SCHEDULED' | 'WAITING' | 'LIVE' | 'PAUSED' | 'FINISHED'
export type Role = 'ADMIN' | 'USER'
export interface Account { id: number; name: string; email: string; role: Role }
export interface AccountSession { user: Account | null; csrf: string | null }
export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE'
export interface Competition { id: number; title: string; description: string; created_at: string; status?: Status; edition_count?: number; participant_count?: number; live_edition_id?: number | null }
export interface Edition {
  id: number; competition_id: number; name: string; description: string; status: Status
  current_index: number; revision: number; total_questions: number; participant_count: number
  created_at: string; started_at: string | null; finished_at: string | null
  scheduled_at: string | null; results_published: boolean; active_participant_count: number
}
export interface Option { id: number; text: string; is_correct?: boolean }
export interface Question { id: number; text: string; type: QuestionType; position: number; options: Option[] }
export interface QuizState extends Edition {
  competition_title: string; question: Question | null; answer_count?: number
  participant?: { id: number; name: string }; answered?: boolean; selected_option_ids?: number[]; csrf?: string
}
export interface PublicEdition extends Edition { competition_title: string; participant_name?: string; is_active?: boolean }
export interface Participant { id: number; name: string; joined_at: string; is_active: boolean; has_account: boolean }
export interface Results {
  edition: Edition; your_score: number | null
  leaderboard: { participant_id: number; name: string; score: number; rank: number }[]
  questions: Question[]; your_answers: { question_id: number; option_ids: number[]; points: number }[]
}
