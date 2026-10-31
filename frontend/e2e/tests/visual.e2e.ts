import { expect, prepare, test } from './setup'

// скриншот-тесты: если вёрстка случайно поедет, снимок не совпадёт с эталоном в snapshots/ и тест покажет
// разницу картинок. Без анимаций, часы и данные закреплены; частицы неба (случайные) скрыты.
// Обновить эталоны после намеренной правки дизайна: make -C frontend e2e-update

const CASES = [
  { name: 'home-light-desktop', path: '/', theme: 'light' as const, width: 1440, height: 900 },
  { name: 'home-dark-mobile', path: '/', theme: 'dark' as const, width: 390, height: 844 },
  { name: 'outlook-light-desktop', path: '/', theme: 'light' as const, width: 1440, height: 900, scroll: '[data-tour="days"]' },
  { name: 'models-light-desktop', path: '/models', theme: 'light' as const, width: 1440, height: 900 },
  { name: 'models-dark-mobile', path: '/models', theme: 'dark' as const, width: 390, height: 844 },
]

for (const c of CASES) {
  test(`скриншот ${c.name}`, async ({ page }) => {
    await page.setViewportSize({ width: c.width, height: c.height })
    await prepare(page, { theme: c.theme, frozen: true })
    await page.goto(c.path)
    await page.waitForLoadState('networkidle')
    await page.evaluate(() => document.fonts.ready)
    if (c.scroll) await page.locator(c.scroll).evaluate((el) => el.scrollIntoView({ block: 'start' }))
    // холст частиц неба во всю шапку – случайный рисунок; графики ECharts в SVG и не задеваются
    await page.addStyleTag({ content: 'canvas.absolute.inset-0 { visibility: hidden }' })
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot(`${c.name}.png`)
  })
}
