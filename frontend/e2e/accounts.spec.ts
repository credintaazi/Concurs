import { test, expect } from '@playwright/test'

test('email accounts, USER authorization, scheduling, pause, resume and stop without speed scoring', async ({ browser, page }) => {
  const password = process.env.E2E_ADMIN_PASSWORD
  if (!password) throw new Error('Set E2E_ADMIN_PASSWORD.')
  const base = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
  const name = `Participant ${Date.now()}`
  const email = `e2e-user-${Date.now()}@example.com`
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const user = await context.newPage()
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  user.on('pageerror', e => errors.push(e.message))
  let cid = 0
  let eid = 0
  let csrf = ''
  try {
    await page.goto('/login')
    await page.getByLabel('Email', { exact: true }).fill(process.env.E2E_ADMIN_EMAIL ?? 'admin@example.com')
    await page.getByLabel('Parolă', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Autentifică-te', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Să înceapă ideile bune.' })).toBeVisible()
    csrf = (await (await page.request.get('/api/v1/auth/session')).json()).csrf
    const headers = { 'X-CSRF-Token': csrf }
    const competition = await (await page.request.post('/api/v1/competitions', { headers, data: { title: `Control extins E2E ${Date.now()}` } })).json()
    cid = competition.id
    const edition = await (await page.request.post(`/api/v1/competitions/${cid}/editions`, { headers, data: { name: `Ediție control ${Date.now()}`, password: 'e2e-edition-password' } })).json()
    eid = edition.id
    for (let i = 0; i < 2; i++) {
      const q = await page.request.post(`/api/v1/editions/${eid}/questions`, { headers, data: { text: `Întrebare control ${i + 1}?`, type: 'SINGLE_CHOICE', options: [{ text: 'Răspuns corect', is_correct: true }, { text: 'Răspuns greșit', is_correct: false }] } })
      expect(q.status()).toBe(201)
    }
    await page.goto(`/admin/editions/${eid}?view=live`)
    await page.getByRole('button', { name: 'Programează', exact: true }).click()
    await page.getByLabel('Data și ora anunțată').fill(new Date(Date.now() + 86400000).toISOString().slice(0, 16))
    await page.getByRole('button', { name: 'Salvează programarea' }).click()
    await expect(page.getByRole('heading', { name: 'Concursul este programat.' })).toBeVisible()
    await user.goto(`${base}/register`)
    await user.getByLabel('Numele tău', { exact: true }).fill(name)
    await user.getByLabel('Email', { exact: true }).fill(email)
    await user.getByLabel('Parolă', { exact: true }).fill('e2e-account-password')
    await user.getByLabel('Confirmă parola', { exact: true }).fill('e2e-account-password')
    await user.getByRole('button', { name: 'Creează contul', exact: true }).click()
    await expect(user.getByRole('link', { name: 'Participările mele' })).toBeVisible()
    expect(await (await user.request.get('/api/v1/auth/session')).json()).toMatchObject({ user: { role: 'USER', email } })
    expect((await user.request.get('/api/v1/competitions')).status()).toBe(403)
    await expect(user.getByRole('link', { name: 'Dashboard', exact: true })).toHaveCount(0)
    await user.goto(`${base}/admin`)
    await expect(user.getByRole('heading', { name: 'Acces rezervat administratorilor.' })).toBeVisible()
    await user.goto(base)
    await expect(user.locator('.account-name')).toContainText(name)
    await user.reload()
    await expect(user.locator('.account-name')).toContainText(name)
    const tile = user.locator('.public-edition').filter({ hasText: edition.name })
    await expect(tile).toContainText('Programat')
    await page.getByRole('button', { name: 'Deschide înscrierile' }).click()
    await expect(tile).toContainText('Înscrieri deschise')
    await tile.click()
    await user.getByRole('link', { name: 'Intră în concurs', exact: true }).click()
    await user.getByLabel('Numele tău', { exact: true }).fill(name)
    await user.getByLabel('Parola ediției', { exact: true }).fill('e2e-edition-password')
    await user.getByRole('button', { name: 'Intră în concurs', exact: true }).click()
    await expect(user.getByRole('heading', { name: `Salut, ${name}!` })).toBeVisible()
    await page.getByRole('button', { name: 'START CONCURS', exact: true }).click()
    await page.getByRole('button', { name: 'Da, START CONCURS', exact: true }).click()
    await expect(user.getByRole('heading', { name: 'Întrebare control 1?' })).toBeVisible()
    await user.getByRole('radio', { name: /Răspuns corect/ }).check()
    await page.getByRole('button', { name: 'Pune pe pauză', exact: true }).click()
    await expect(user.getByText('Concursul este în pauză', { exact: true })).toBeVisible()
    await expect(user.getByRole('radio', { name: /Răspuns corect/ })).toBeChecked()
    await expect(user.getByRole('button', { name: 'Trimite răspunsul' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Următoarea întrebare' })).toBeDisabled()
    const paused = await (await user.request.get(`/api/v1/editions/${eid}/state`)).json()
    expect((await user.request.post(`/api/v1/editions/${eid}/answers`, { headers: { 'X-CSRF-Token': paused.csrf }, data: { question_id: paused.question.id, option_ids: [paused.question.options[0].id] } })).status()).toBe(409)
    await user.screenshot({ path: 'test-results/pause-mobile.png', fullPage: true })
    await page.screenshot({ path: 'test-results/controls-paused-desktop.png', fullPage: true })
    await page.getByRole('button', { name: 'Reia concursul', exact: true }).click()
    await expect(user.getByRole('button', { name: 'Trimite răspunsul' })).toBeEnabled()
    await user.getByRole('button', { name: 'Trimite răspunsul' }).click()
    await expect(user.getByText('Răspuns înregistrat!', { exact: true })).toBeVisible()
    await expect(page.locator('.live-score-panel .leaderboard-row').first()).toContainText('1')
    await user.reload()
    await expect(user.getByText('Răspuns înregistrat!', { exact: true })).toBeVisible()
    // Logging out makes account-bound participation inaccessible. Logging in restores it.
    await user.getByRole('button', { name: 'Deconectare', exact: true }).click()
    await user.getByRole('link', { name: 'Autentificare', exact: true }).click()
    await user.getByLabel('Email', { exact: true }).fill(email)
    await user.getByLabel('Parolă', { exact: true }).fill('e2e-account-password')
    await user.getByRole('button', { name: 'Autentifică-te', exact: true }).click()
    await user.getByRole('link', { name: 'Participările mele', exact: true }).click()
    await user.getByRole('heading', { name: edition.name, exact: true }).click()
    await expect(user.getByText('Răspuns înregistrat!', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Încheie anticipat', exact: true }).click()
    await page.getByRole('button', { name: 'Încheie acum și publică rezultatele', exact: true }).click()
    await expect(user.getByRole('heading', { name: 'Clasamentul final', exact: true })).toBeVisible()
    await expect(user.locator('.your-score')).toContainText('1 / 2')
    expect(await user.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    expect(errors).toEqual([])
  } finally {
    await context.close()
    if (cid && csrf) {
      const headers = { 'X-CSRF-Token': csrf }
      if (eid) {
        const stateResponse = await page.request.get(`/api/v1/editions/${eid}/admin-state`)
        if (stateResponse.ok()) {
          const state = await stateResponse.json()
          if (['LIVE', 'PAUSED'].includes(state.status)) await page.request.post(`/api/v1/editions/${eid}/stop`, { headers, data: { expected_revision: state.revision } })
        }
      }
      await page.request.delete(`/api/v1/competitions/${cid}`, { headers })
    }
  }
})
