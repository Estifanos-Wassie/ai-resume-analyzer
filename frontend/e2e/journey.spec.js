import { expect, test } from '@playwright/test'

const api = 'http://127.0.0.1:8001'
const valid = { match_score: 75, strengths: ['Synthetic Python experience'], missing_skills: [], suggestions: ['Add evidence'] }
let syntheticPdf

test.beforeEach(async ({ page, request }) => {
  await request.post(`${api}/__test/reset`)
  syntheticPdf = await (await request.get(`${api}/__test/pdf`)).body()
  await page.route('**/*', (route) => {
    const host = new URL(route.request().url()).hostname
    return ['127.0.0.1', 'localhost'].includes(host) ? route.continue() : route.abort()
  })
  await page.goto('/')
})

async function upload(page, buffer = syntheticPdf, name = 'synthetic-resume.PDF') {
  await page.getByLabel('Resume PDF', { exact: true }).setInputFiles({ name, mimeType: 'application/pdf', buffer })
}
const analyze = (page) => page.getByRole('button', { name: 'Analyze resume', exact: true })

test('actual FastAPI: oversized token input is rejected before provider, then shortened manually', async ({ page, request }) => {
  await upload(page)
  const description = '😀'.repeat(5000)
  await page.getByLabel('Job description').fill(description)
  await analyze(page).click()
  await expect(page.getByRole('alert')).toContainText('Shorten either input')
  await expect(page.getByRole('alert')).toContainText('No analysis was sent')
  await expect(page.getByLabel('Job description')).toHaveValue(description)
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(0)
  await page.getByLabel('Job description').fill('Synthetic Python developer')
  await analyze(page).click()
  await expect(page.getByRole('heading', { name: 'Your feedback' })).toBeVisible()
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(1)
})

async function screenshot(page, testInfo, name) {
  await page.screenshot({ path: `test-results/screenshots/${testInfo.project.name}-${name}.png`, fullPage: true, animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

test('actual FastAPI: keyboard upload, extraction, provider error, manual retry, history and clearing', async ({ page, request }, testInfo) => {
  await page.clock.install()
  await page.clock.pauseAt(new Date())
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Resume PDF', { exact: true })).toBeFocused()
  const chooserPromise = page.waitForEvent('filechooser')
  await page.keyboard.press('Enter')
  const chooser = await chooserPromise
  await chooser.setFiles({ name: 'synthetic-resume.PDF', mimeType: 'application/pdf', buffer: syntheticPdf })
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Job description')).toBeFocused()
  await page.getByLabel('Job description').fill('Python developer SYNTHETIC_RETRY_ONCE')
  await analyze(page).click()
  await expect(page.getByRole('alert')).toContainText('temporarily unavailable')
  await expect(page.getByLabel('Job description')).toHaveValue('Python developer SYNTHETIC_RETRY_ONCE')
  await expect(page.getByText(/Retry manually in/)).toBeVisible()
  await screenshot(page, testInfo, 'provider-error')
  await page.clock.fastForward(1000)
  await expect(analyze(page)).toBeEnabled()
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(1)
  await analyze(page).click()
  await expect(page.getByRole('heading', { name: 'Your feedback' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Your feedback' })).toBeFocused()
  await expect(page.getByText('Synthetic PDF text extracted successfully')).toBeVisible()
  await expect(page.getByText('88%', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Session history' })).toBeVisible()
  await screenshot(page, testInfo, 'feedback')
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(2)
  await page.getByRole('button', { name: 'Clear session' }).click()
  await expect(page.getByLabel('Resume PDF', { exact: true })).toBeFocused()
  await expect(page.getByLabel('Job description')).toHaveValue('')
  await expect(page.getByText('No file selected')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Your feedback' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Session history' })).toHaveCount(0)
  await expect(page.getByRole('status')).toContainText('Session cleared')
  await screenshot(page, testInfo, 'cleared')
})

test('validation in the browser and actual backend: invalid drop, whitespace, blank and corrupt PDFs', async ({ page, request }, testInfo) => {
  await analyze(page).click()
  await expect(page.locator('#resume-error')).toBeVisible()
  await expect(page.locator('#description-error')).toBeVisible()
  const dataTransfer = await page.evaluateHandle(() => {
    const data = new DataTransfer()
    data.items.add(new File(['synthetic'], 'one.pdf', { type: 'application/pdf' }))
    data.items.add(new File(['synthetic'], 'two.pdf', { type: 'application/pdf' }))
    return data
  })
  await page.locator('.file-drop').dispatchEvent('drop', { dataTransfer })
  await expect(page.locator('#resume-error')).toContainText('exactly one')
  const singleDrop = await page.evaluateHandle((bytes) => {
    const data = new DataTransfer()
    data.items.add(new File([new Uint8Array(bytes)], 'synthetic-dropped.pdf', { type: 'application/pdf' }))
    return data
  }, Array.from(syntheticPdf))
  await page.locator('.file-drop').dispatchEvent('drop', { dataTransfer: singleDrop })
  await expect(page.getByText('Selected: synthetic-dropped.pdf')).toBeVisible()
  await page.getByLabel('Job description').fill('   ')
  await analyze(page).click()
  await expect(page.locator('#description-error')).toContainText('not just spaces')
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(0)
  const blank = await (await request.get(`${api}/__test/pdf?kind=blank`)).body()
  await upload(page, blank)
  await page.getByLabel('Job description').fill('Synthetic Python job')
  await analyze(page).click()
  await expect(page.locator('#resume-error')).toContainText('text-based PDF')
  await upload(page, Buffer.from('not a real PDF'))
  await analyze(page).click()
  await expect(page.locator('#resume-error')).toContainText('could not be read')
  await screenshot(page, testInfo, 'validation')
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(0)
  await upload(page)
  await analyze(page).click()
  await expect(page.getByText('88%', { exact: true })).toBeVisible()
})

test('actual multipart Unicode and newline counts agree at the 20,000-character boundary', async ({ page, request }) => {
  await upload(page)
  // Compressible filler isolates the character ceiling from the token ceiling.
  const job = 'x'.repeat(19_996) + '😀\ny'
  await page.getByLabel('Job description').fill(job)
  await expect(page.locator('#description-count')).toHaveText('20,000 / 20,000 characters')
  await analyze(page).click()
  await expect(page.getByText('88%', { exact: true })).toBeVisible()
  await page.getByLabel('Job description').fill('😀' + job)
  await expect(page.locator('#description-error')).toContainText('20,000')
  await analyze(page).click()
  expect((await (await request.get(`${api}/__test/state`)).json()).provider_calls).toBe(1)
})

test('controlled malformed responses, validation arrays, network failure, and manual retry', async ({ page }) => {
  const responses = [
    { status: 422, json: { detail: [{ loc: ['body', 'job_description'], msg: 'SENSITIVE_TRACE', input: 'SENSITIVE_TEXT' }] } },
    { status: 200, json: { match_score: '75' } },
    { status: 200, contentType: 'text/html', body: '<html>SENSITIVE_TRACE</html>' },
    null,
    { status: 200, json: valid },
  ]
  let count = 0
  await page.route(`${api}/analyze`, async (route) => {
    const response = responses[count++]
    if (!response) await route.abort('failed')
    else await route.fulfill(response)
  })
  await upload(page)
  await page.getByLabel('Job description').fill('Synthetic developer role')
  for (let index = 0; index < 4; index++) {
    await analyze(page).click()
    await expect(page.getByRole('alert').last()).toBeVisible()
    await expect(page.locator('body')).not.toContainText('SENSITIVE_')
    await expect(page.getByRole('heading', { name: 'Your feedback' })).toHaveCount(0)
    expect(count).toBe(index + 1)
  }
  await analyze(page).click()
  await expect(page.getByText('75%', { exact: true })).toBeVisible()
  expect(count).toBe(5)
})

test('pending request is single, cancelled by edits, and cannot restore stale feedback', async ({ page }) => {
  let count = 0
  let release
  const gate = new Promise((resolve) => { release = resolve })
  await page.route(`${api}/analyze`, async (route) => {
    count++
    if (count === 1) {
      await gate
      await route.fulfill({ json: { ...valid, match_score: 10 } }).catch(() => {})
    } else await route.fulfill({ json: { ...valid, match_score: 90 } })
  })
  await upload(page)
  await page.getByLabel('Job description').fill('Original job')
  await analyze(page).click()
  await expect(page.getByRole('button', { name: 'Analyzing…' })).toBeDisabled()
  await expect.poll(() => count).toBe(1)
  await page.locator('form').evaluate((form) => { form.requestSubmit(); form.requestSubmit() })
  expect(count).toBe(1)
  await page.getByLabel('Job description').fill('New job')
  await analyze(page).click()
  await expect(page.getByText('90%', { exact: true })).toBeVisible()
  release()
  await expect(page.getByText('10%', { exact: true })).toHaveCount(0)
  expect(count).toBe(2)
})
