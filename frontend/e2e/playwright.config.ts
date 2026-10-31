import { defineConfig, devices } from '@playwright/test'

// браузерные тесты сайта: Chromium в контейнере, сайт – служба site из compose.yml; эталонные скриншоты –
// в snapshots/ (снимаются в том же образе, поэтому совпадают пиксель в пиксель локально и в CI)
export default defineConfig({
  testDir: 'tests',
  testMatch: '**/*.e2e.ts',
  snapshotPathTemplate: '{testDir}/../snapshots/{arg}{ext}',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  workers: 2,
  reporter: [['list']],
  outputDir: 'test-results',
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: 'disabled' } },
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8080',
    locale: 'ru-RU',
    timezoneId: 'Asia/Almaty',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // WebGL для карты в контейнере без видеокарты – программный рендер SwiftShader
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
})
