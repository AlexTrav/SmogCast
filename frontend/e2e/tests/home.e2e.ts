import { expect, fixture, prepare, test } from './setup'

// главная: цифра и подписи, прогноз по дням и часам, советы, «Обновить сейчас», подробный график

const one = (v: number) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v)

test.describe('главная', () => {
  test('цифра PM2.5, подпись источника, три дня, лента на 72 часа и четыре совета', async ({ page, errors }) => {
    await prepare(page)
    await page.goto('/')
    const status = fixture('status')
    await expect(page.locator('[data-tour="hero"]')).toContainText(one(status.pm2_5))
    await expect(page.getByText('в среднем по городу · оценка модели CAMS')).toBeVisible()
    await expect(page.locator('[data-tour="days"] li')).toHaveCount(3)
    // «сейчас» и 72 часа прогноза
    await expect(page.locator('ol[aria-label="По часам"] > li')).toHaveCount(73)
    await expect(page.locator('section[data-tour="best"] li')).toHaveCount(4)
    expect(errors).toEqual([])
  })

  test('«Пересчитать прогноз»: свежесть данных и время моделей плашкой, затем сервер просит подождать', async ({ page, errors }) => {
    await prepare(page)
    await page.goto('/')
    await page.getByRole('button', { name: 'Пересчитать прогноз', exact: true }).click()
    const card = page.getByRole('status').filter({ hasText: 'Модели пересчитали' })
    await expect(card).toContainText('Модели пересчитали прогноз за 4,7 мс')
    await expect(card).toContainText('самые свежие')
    await expect(card).toContainText('Совпадает с ежечасным расчётом')
    await expect(page.getByRole('button', { name: /Ещё \d+ с/ })).toBeDisabled()
    // после перезагрузки сервер помнит адрес и отвечает 429 – сайт показывает, сколько ждать
    await page.reload()
    await page.getByRole('button', { name: 'Пересчитать прогноз', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Не чаще раза в 30 секунд' })).toContainText('подождите 28 с')
    expect(errors).toEqual([])
  })

  test('тумблер чувствительности делает советы и вывод на день строже', async ({ page }) => {
    await prepare(page)
    await page.goto('/')
    const tips = page.locator('section[data-tour="best"]')
    const level = fixture('status').level
    await page.getByRole('switch').check({ force: true })
    // при умеренном воздухе обычным людям «можно», чувствительным – «лучше сократить»
    if (level === 'moderate') {
      await expect(tips).toContainText('Лучше сократить')
      await expect(page.locator('[data-tour="days"]')).toContainText('Прогулки покороче')
    }
    expect(await page.evaluate(() => localStorage.getItem('smogcast-sensitive'))).toBe('1')
  })

  test('подробный график: горизонт, сравнение моделей, разброс – только для одной модели', async ({ page, errors }) => {
    await prepare(page)
    await page.goto('/')
    await page.getByRole('button', { name: /Подробнее/ }).click()
    await expect(page.locator('#details [_echarts_instance_]')).toBeVisible()
    await page.getByRole('radio', { name: '1 сутки' }).click()
    await expect(page.getByRole('radio', { name: '1 сутки' })).toHaveAttribute('aria-checked', 'true')
    const spread = page.getByRole('checkbox', { name: 'Разброс прогноза' })
    await expect(spread).toBeEnabled()
    await page.getByRole('checkbox', { name: 'ARIMA' }).click()
    await expect(spread).toBeDisabled()
    await expect(page.locator('#details ul').filter({ hasText: 'Факт' })).toContainText('ARIMA')
    expect(errors).toEqual([])
  })
})
