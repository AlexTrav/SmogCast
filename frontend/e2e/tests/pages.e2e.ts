import { expect, prepare, test } from './setup'

// каждая страница открывается без ошибок JavaScript и показывает свой заголовок; экскурсия; карта

const PAGES = [
  { path: '/', heading: 'Что будет с воздухом' },
  { path: '/map', heading: 'Смог над долиной' },
  { path: '/history', heading: 'Четыре года воздуха Алматы' },
  { path: '/models', heading: 'Насколько точен прогноз' },
  { path: '/performance', heading: 'Как работает система реального времени' },
  { path: '/about', heading: 'Прогноз смога в Алматы' },
]

for (const p of PAGES) {
  test(`страница ${p.path} открывается без ошибок`, async ({ page, errors }) => {
    await prepare(page)
    await page.goto(p.path)
    await expect(page.getByRole('heading', { name: p.heading })).toBeVisible()
    expect(errors).toEqual([])
  })
}

test('экскурсия при первом визите: четыре шага и больше не показывается', async ({ page }) => {
  await prepare(page, { tour: true })
  await page.goto('/')
  const dialog = page.getByRole('dialog')
  for (const title of ['Воздух сейчас', 'Три дня вперёд', 'Что делать', 'Подробности']) {
    await expect(dialog.getByRole('heading')).toHaveText(title)
    await dialog.getByRole('button', { name: title === 'Подробности' ? 'Понятно' : 'Далее' }).click()
  }
  await expect(dialog).toHaveCount(0)
  expect(await page.evaluate(() => localStorage.getItem('smogcast-tour'))).toBe('done')
  await page.reload()
  await page.waitForTimeout(2000)
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('карта: 25 клеток сетки, клетка Алматы, проигрывание часов', async ({ page, errors }) => {
  await prepare(page)
  await page.goto('/map')
  await expect(page.locator('.map-chip')).toHaveCount(25)
  await expect(page.locator('.map-chip.map-city')).toHaveCount(1)
  const time = page.locator('span.num.whitespace-nowrap').first()
  const before = await time.innerText()
  await page.getByRole('button', { name: 'Проиграть' }).click()
  await expect(time).not.toHaveText(before)
  await page.getByRole('button', { name: 'Пауза' }).click()
  expect(errors).toEqual([])
})
