import { test, expect } from '@playwright/test'
import type { BrowserContext, Page } from '@playwright/test'

test('admin and three participants complete a real five-question competition', async ({ browser, page }) => {
  const password = process.env.E2E_ADMIN_PASSWORD
  if (!password) throw new Error('Set E2E_ADMIN_PASSWORD and optionally E2E_ADMIN_USERNAME for the running app.')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const contexts: BrowserContext[] = []
  let competitionId = 0
  let csrf = ''
  const base = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
  const title = `Cultură Generală E2E ${Date.now()}`
  try {
    await page.goto('/admin/login')
    await page.getByLabel('Email', { exact: true }).fill(process.env.E2E_ADMIN_EMAIL ?? 'admin@example.com')
    await page.getByLabel('Parolă', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Autentifică-te', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Să înceapă ideile bune.' })).toBeVisible()
    await page.getByRole('button', { name: 'Concurs nou', exact: true }).click()
    await page.getByLabel('Titlul concursului').fill(title)
    await page.getByLabel('Descriere', { exact: true }).fill('Created by the acceptance test; removed after the test.')
    await page.getByRole('button', { name: 'Salvează concursul' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.getByRole('link', { name: title, exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/competitions\/\d+$/)
    competitionId = Number(page.url().split('/').pop())
    csrf = (await (await page.request.get('/api/v1/admin/session')).json()).csrf
    await page.getByRole('button', { name: 'Ediție nouă' }).click()
    await page.getByLabel('Numele ediției').fill('Ediția 1')
    await page.getByLabel('Parola de participare').fill('edition-e2e-password')
    await page.getByRole('button', { name: 'Salvează ediția' }).click()
    await expect(page).toHaveURL(/\/admin\/editions\/\d+$/)
    const editionId = Number(page.url().split('/').pop())
    for (let i = 1; i <= 5; i++) {
      await page.getByRole('button', { name: 'Adaugă întrebare', exact: true }).click()
      await page.getByLabel('Întrebarea', { exact: true }).fill(`Întrebarea de verificare ${i}?`)
      if (i % 2 === 0) await page.getByLabel('Tipul răspunsului').selectOption('MULTIPLE_CHOICE')
      for (let j = 1; j <= 4; j++) await page.getByLabel(`Text varianta ${j}`, { exact: true }).fill(`Varianta ${j}`)
      await page.getByLabel('Varianta 1 corectă', { exact: true }).check()
      if (i % 2 === 0) await page.getByLabel('Varianta 2 corectă', { exact: true }).check()
      await page.getByRole('button', { name: 'Salvează întrebarea' }).click()
      await expect(page.getByRole('dialog')).toHaveCount(0)
    }
    await page.getByRole('tab', { name: 'Control live' }).click()
    await page.getByRole('button', { name: 'Deschide înscrierile' }).click()
    await expect(page.getByRole('button', { name: 'START CONCURS' })).toBeEnabled()
    const players: Page[] = []
    for (const name of ['Andrei', 'Maria', 'Bogdan']) {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
      contexts.push(context)
      const player = await context.newPage()
      player.on('pageerror', error => errors.push(error.message))
      await player.goto(`${base}/join/${editionId}`)
      await player.getByLabel('Numele tău', { exact: true }).fill(name)
      await player.getByLabel('Parola ediției', { exact: true }).fill('edition-e2e-password')
      await player.getByRole('button', { name: 'Intră în concurs' }).click()
      await expect(player.getByRole('heading', { name: `Salut, ${name}!` })).toBeVisible()
      await expect(player.getByText('Conectat în timp real')).toBeVisible()
      players.push(player)
    }
    await expect(players[0].locator('.waiting-count')).toContainText('3')
    await players[0].screenshot({ path: 'test-results/waiting-mobile.png', fullPage: true })
    await page.getByRole('button', { name: 'START CONCURS', exact: true }).click()
    await page.getByRole('button', { name: 'Da, START CONCURS', exact: true }).click()
    for (const player of players) await expect(player.getByRole('heading', { name: 'Întrebarea de verificare 1?' })).toBeVisible()
    const lateContext = await browser.newContext()
    contexts.push(lateContext)
    const late = await lateContext.newPage()
    await late.goto(`${base}/join/${editionId}`)
    await expect(late.getByRole('heading', { name: 'Concursul a început deja.' })).toBeVisible()
    // Cookie sessions persist across reload. No extra join is required after START.
    await players[0].reload()
    await expect(players[0].getByRole('heading', { name: 'Întrebarea de verificare 1?' })).toBeVisible()
    for (let i = 1; i <= 5; i++) {
      for (let j = 0; j < players.length; j++) {
        const player = players[j]
        await expect(player.getByRole('heading', { name: `Întrebarea de verificare ${i}?` })).toBeVisible()
        await expect(player.getByText('Conectat în timp real')).toBeVisible()
        await player.getByRole(i % 2 === 0 ? 'checkbox' : 'radio', { name: /Varianta 1/ }).check()
        if (i % 2 === 0 && j === 0) await player.getByRole('checkbox', { name: /Varianta 2/ }).check()
        if (i === 2 && j === 0) await player.screenshot({ path: 'test-results/question-mobile.png', fullPage: true })
        await player.getByRole('button', { name: 'Trimite răspunsul' }).click()
        await expect(player.getByText('Răspuns înregistrat!')).toBeVisible()
      }
      if (i === 1) {
        await players[0].reload()
        await expect(players[0].getByText('Răspuns înregistrat!')).toBeVisible()
        await page.screenshot({ path: 'test-results/live-desktop.png', fullPage: true })
      }
      if (i === 2) {
        // A dropped socket reconnects and reloads the authoritative state.
        await contexts[0].setOffline(true)
        await expect(players[0].getByText(/Conexiune pierdută|Se conectează/)).toBeVisible({ timeout: 35000 })
        await contexts[0].setOffline(false)
        await expect(players[0].getByText('Conectat în timp real')).toBeVisible({ timeout: 20000 })
        await expect(players[0].getByText('Răspuns înregistrat!')).toBeVisible()
      }
      if (i < 5) await page.getByRole('button', { name: 'Următoarea întrebare', exact: true }).click()
    }
    await page.getByRole('button', { name: 'Finalizează concursul', exact: true }).click()
    await page.getByRole('button', { name: 'Finalizează și arată rezultatele' }).click()
    for (let i = 0; i < players.length; i++) {
      await expect(players[i].getByRole('heading', { name: 'Clasamentul final' })).toBeVisible()
      await expect(players[i].locator('.your-score')).toContainText(`${i === 0 ? 5 : 3} / 5`)
      await expect(players[i].locator('.leaderboard-row')).toHaveCount(3)
      await expect(players[i].locator('.leaderboard-row').nth(1).locator('.rank')).toHaveText('2')
      await expect(players[i].locator('.leaderboard-row').nth(2).locator('.rank')).toHaveText('2')
      expect(await players[i].evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    }
    await players[0].screenshot({ path: 'test-results/results-mobile.png', fullPage: true })
    await page.getByRole('tab', { name: 'Rezultate' }).click()
    await expect(page.getByRole('heading', { name: 'Clasamentul final' })).toBeVisible()
    await page.screenshot({ path: 'test-results/results-desktop.png', fullPage: true })
    expect(errors).toEqual([])
  } finally {
    for (const context of contexts) await context.close()
    if (competitionId && csrf) {
      // The normal deletion endpoint deliberately rejects LIVE editions. Finish through
      // remaining questions first if a UI assertion failed mid-competition.
      const editionsResponse = await page.request.get(`/api/v1/competitions/${competitionId}/editions`)
      if (editionsResponse.ok()) for (const e of await editionsResponse.json()) {
        if (e.status === 'LIVE') {
          for (let i = 0; i < e.total_questions; i++) {
            const s = await (await page.request.get(`/api/v1/editions/${e.id}/admin-state`)).json()
            if (s.current_index === s.total_questions - 1) {
              await page.request.post(`/api/v1/editions/${e.id}/finish`, { headers: { 'X-CSRF-Token': csrf } }); break
            }
            await page.request.post(`/api/v1/editions/${e.id}/next`, { headers: { 'X-CSRF-Token': csrf }, data: { expected_question_id: s.question.id } })
          }
        }
      }
      await page.request.delete(`/api/v1/competitions/${competitionId}`, { headers: { 'X-CSRF-Token': csrf } })
    }
  }
})
