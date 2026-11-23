import { chromium } from '../frontend/node_modules/playwright/index.mjs'

const output = process.argv[2]
if (!output) throw new Error('Se requiere la ruta de salida')

const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 })
await page.goto('http://127.0.0.1:4175/login', { waitUntil: 'networkidle' })
await page.screenshot({ path: output, fullPage: true })
await browser.close()
