import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure', colorScheme: 'light' },
  projects: [
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1280, height: 1000 } } },
    { name: 'mobile', use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: [
    {
      command: '../backend/venv/bin/python ../backend/tests/e2e_server.py',
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: false,
      env: { PYTHON_DOTENV_DISABLED: '1', GROQ_API_KEY: '', PYTHONDONTWRITEBYTECODE: '1' },
    },
    {
      command: 'npm run build -- --outDir node_modules/.cache/e2e-site && npm run preview -- --outDir node_modules/.cache/e2e-site --host 127.0.0.1 --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8001///' },
    },
  ],
})
