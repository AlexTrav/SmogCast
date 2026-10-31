import { expect, prepare, test } from './setup'

// подсказки «?»: на каждой странице каждая видимая подсказка открывается и показывает название и объяснение.
// Полноту переводов на казахском и английском проверяет Vitest (src/locales/locales.spec.ts) – без браузера

const PAGES = ['/', '/map', '/history', '/models', '/performance', '/about']
const LOCALES = ['ru'] as const

for (const locale of LOCALES) {
  for (const path of PAGES) {
    test(`подсказки ${path} (${locale})`, async ({ page }) => {
      test.setTimeout(120_000)
      await prepare(page, { locale })
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      if (path === '/') await page.locator('[data-tour="more"]').click() // подсказки подробного графика
      // блоки с v-reveal появляются при прокрутке
      for (let y = 0; y < 8000; y += 600) await page.mouse.wheel(0, 600)
      const hints = page.locator('button[aria-expanded][aria-label]').filter({ hasText: '?' })
      const count = await hints.count()
      expect(count).toBeGreaterThan(path === '/' ? 30 : 4)
      for (let i = 0; i < count; i++) {
        const hint = hints.nth(i)
        if (!(await hint.isVisible())) continue
        await hint.evaluate((el) => el.scrollIntoView({ block: 'center' }))
        await hint.click()
        const tip = page.getByRole('tooltip')
        await expect(tip).toBeVisible()
        const text = await tip.innerText()
        expect(text, await hint.getAttribute('aria-label') ?? '').not.toContain('terms.')
        expect(text.length).toBeGreaterThan(40)
        await page.keyboard.press('Escape')
      }
    })
  }
}
