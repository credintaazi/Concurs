import { useFieldArray, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Trash2 } from 'lucide-react'
import { ErrorNotice } from './components'
import type { Competition, Edition, Question } from './types'

const title = z.string().trim().min(1, 'Completează acest câmp.').max(200, 'Maximum 200 de caractere.')
const description = z.string().max(5000)
const competitionSchema = z.object({ title, description })
const editionSchema = z.object({ name: title, description, password: z.string().max(128).refine(v => !v || v.length >= 8, 'Parola trebuie să aibă minimum 8 caractere.') })
export type CompetitionValues = z.infer<typeof competitionSchema>
export type EditionValues = z.infer<typeof editionSchema>

export function CompetitionForm({ value, save, pending, error }: { value?: Competition; save: (value: CompetitionValues) => void; pending: boolean; error?: unknown }) {
  const { register, handleSubmit, formState: { errors } } = useForm({ resolver: zodResolver(competitionSchema), defaultValues: { title: value?.title ?? '', description: value?.description ?? '' } })
  return <form onSubmit={handleSubmit(save)} className="form"><label>Titlul concursului<input {...register('title')} placeholder="ex. Concurs biblic" autoFocus/></label><small className="field-error">{errors.title?.message}</small><label>Descriere<textarea {...register('description')} placeholder="Despre ce este concursul?" rows={3}/></label><small className="field-error">{errors.description?.message}</small><ErrorNotice error={error}/><button className="button primary" disabled={pending}>{pending ? 'Se salvează…' : 'Salvează concursul'}</button></form>
}

export function EditionForm({ value, save, pending, error }: { value?: Edition; save: (value: EditionValues) => void; pending: boolean; error?: unknown }) {
  const { register, handleSubmit, setError, formState: { errors } } = useForm({ resolver: zodResolver(editionSchema), defaultValues: { name: value?.name ?? '', description: value?.description ?? '', password: '' } })
  return <form className="form" onSubmit={handleSubmit(v => {
    if (!value && !v.password) { setError('password', { message: 'Configurează parola de participare.' }); return }
    save(v)
  })}><label>Numele ediției<input {...register('name')} placeholder="ex. Ediția de toamnă 2026" autoFocus/></label><small className="field-error">{errors.name?.message}</small><label>Descriere<textarea {...register('description')} rows={3}/></label><label>{value ? 'Parolă nouă (opțional)' : 'Parola de participare'}<input {...register('password')} type="password" autoComplete="new-password" placeholder="Minimum 8 caractere" disabled={!!value && ['LIVE', 'PAUSED'].includes(value.status)}/></label><small className="field-error">{errors.password?.message}</small><p className="hint">{value ? 'Lasă parola goală pentru a o păstra pe cea existentă.' : 'Participanții vor folosi această parolă pentru a intra în ediție.'}</p><ErrorNotice error={error}/><button className="button primary" disabled={pending}>{pending ? 'Se salvează…' : 'Salvează ediția'}</button></form>
}

export const questionSchema = z.object({
  text: z.string().trim().min(1, 'Scrie textul întrebării.').max(10000),
  type: z.enum(['SINGLE_CHOICE', 'MULTIPLE_CHOICE']),
  options: z.array(z.object({ text: z.string().trim().min(1, 'Completează varianta.').max(2000), is_correct: z.boolean() })).min(2, 'Adaugă minimum două variante.').max(20),
}).superRefine((v, ctx) => {
  const count = v.options.filter(o => o.is_correct).length
  if ((v.type === 'SINGLE_CHOICE' && count !== 1) || (v.type === 'MULTIPLE_CHOICE' && count < 2))
    ctx.addIssue({ code: 'custom', path: ['root'], message: v.type === 'SINGLE_CHOICE' ? 'Marchează exact o variantă corectă.' : 'Marchează cel puțin două variante corecte.' })
})
export type QuestionValues = z.infer<typeof questionSchema>

export function QuestionForm({ value, save, pending, error }: { value?: Question; save: (v: QuestionValues) => void; pending: boolean; error?: unknown }) {
  const { register, handleSubmit, control, watch, setValue, formState: { errors } } = useForm<QuestionValues>({ resolver: zodResolver(questionSchema), defaultValues: value ? { text: value.text, type: value.type, options: value.options.map(o => ({ text: o.text, is_correct: !!o.is_correct })) } : { text: '', type: 'SINGLE_CHOICE', options: [{ text: '', is_correct: false }, { text: '', is_correct: false }, { text: '', is_correct: false }, { text: '', is_correct: false }] } })
  const { fields, append, remove } = useFieldArray({ control, name: 'options' })
  const type = watch('type')
  const options = watch('options')
  return <form className="form" onSubmit={handleSubmit(save)}><label>Întrebarea<textarea {...register('text')} rows={3} placeholder="Scrie întrebarea aici…" autoFocus/></label><small className="field-error">{errors.text?.message}</small><label>Tipul răspunsului<select {...register('type')} onChange={e => {
    setValue('type', e.target.value as QuestionValues['type'])
    if (e.target.value === 'SINGLE_CHOICE') { let first = true; options.forEach((o, i) => { setValue(`options.${i}.is_correct`, o.is_correct && first); if (o.is_correct) first = false }) }
  }}><option value="SINGLE_CHOICE">Un singur răspuns corect</option><option value="MULTIPLE_CHOICE">Mai multe răspunsuri corecte</option></select></label><div className="section-label">VARIANTE DE RĂSPUNS <span>Marchează variantele corecte</span></div><div className="option-editor">{fields.map((field, i) => <div key={field.id}><div className={`option-edit-row ${options[i]?.is_correct ? 'correct' : ''}`}><input type={type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'} name="correct-option" aria-label={`Varianta ${i + 1} corectă`} checked={options[i]?.is_correct ?? false} onChange={e => {
    if (type === 'SINGLE_CHOICE') options.forEach((_, j) => setValue(`options.${j}.is_correct`, j === i, { shouldValidate: true }))
    else setValue(`options.${i}.is_correct`, e.target.checked, { shouldValidate: true })
  }}/><span className="option-letter">{String.fromCharCode(65 + i)}</span><input {...register(`options.${i}.text`)} aria-label={`Text varianta ${i + 1}`} placeholder={`Varianta ${i + 1}`}/><button type="button" className="icon-button" disabled={fields.length <= 2} onClick={() => remove(i)} aria-label={`Șterge varianta ${i + 1}`}><Trash2 size={16}/></button></div><small className="field-error">{errors.options?.[i]?.text?.message}</small></div>)}</div><button className="button secondary" type="button" disabled={fields.length >= 20} onClick={() => append({ text: '', is_correct: false })}><Plus size={16}/>Adaugă variantă</button><small className="field-error">{errors.root?.message ?? errors.options?.message}</small><ErrorNotice error={error}/><button className="button primary" disabled={pending}>{pending ? 'Se salvează…' : 'Salvează întrebarea'}</button></form>
}
