import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const outputDir = path.join(root, 'tmp', 'degree-document', 'captures-wide')
const profileDir = path.join(root, 'tmp', 'degree-document', 'chrome-capture-profile')
const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const frontend = 'http://127.0.0.1:5173'
const backend = 'http://127.0.0.1:8000'
const port = 9223

const adminPassword = process.env.NEORX_CAPTURE_ADMIN_PASSWORD
const doctorPassword = process.env.NEORX_CAPTURE_DOCTOR_PASSWORD
if (!adminPassword || !doctorPassword) {
  throw new Error('Capture credentials were not provided through the process environment.')
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function waitForJson(url, attempts = 60) {
  for (let index = 0; index < attempts; index += 1) {
    try {
      const response = await fetch(url)
      if (response.ok) return response.json()
    } catch { /* Browser is still starting. */ }
    await sleep(250)
  }
  throw new Error(`Timed out waiting for ${url}`)
}

class CdpClient {
  constructor(url) {
    this.socket = new WebSocket(url)
    this.nextId = 1
    this.pending = new Map()
    this.events = new Map()
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true })
      this.socket.addEventListener('error', reject, { once: true })
    })
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.id) {
        const request = this.pending.get(message.id)
        if (!request) return
        this.pending.delete(message.id)
        if (message.error) request.reject(new Error(message.error.message))
        else request.resolve(message.result)
        return
      }
      const listeners = this.events.get(message.method) || []
      this.events.set(message.method, [])
      for (const listener of listeners) listener(message.params)
    })
  }

  send(method, params = {}) {
    const id = this.nextId
    this.nextId += 1
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.socket.send(JSON.stringify({ id, method, params }))
    })
  }

  waitFor(method, timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      const listeners = this.events.get(method) || []
      listeners.push(resolve)
      this.events.set(method, listeners)
      setTimeout(() => reject(new Error(`Timed out waiting for ${method}`)), timeoutMs)
    })
  }

  close() {
    this.socket.close()
  }
}

async function token(username, password) {
  const response = await fetch(`${backend}/api/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, remember_me: false }),
  })
  if (!response.ok) throw new Error(`Login failed for ${username}: ${response.status}`)
  return response.json()
}

async function main() {
  await mkdir(outputDir, { recursive: true })
  await mkdir(profileDir, { recursive: true })

  const chrome = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--window-size=1440,900',
    '--force-device-scale-factor=1',
    '--hide-scrollbars',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-allow-origins=*',
    'about:blank',
  ], { stdio: 'ignore' })

  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`)
    const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(frontend)}`, { method: 'PUT' })
    const target = await targetResponse.json()
    const cdp = new CdpClient(target.webSocketDebuggerUrl)
    await cdp.open()
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    })

    async function evaluate(expression) {
      const result = await cdp.send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
      })
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'Evaluation failed')
      return result.result.value
    }

    async function navigate(route) {
      const loaded = cdp.waitFor('Page.loadEventFired')
      await cdp.send('Page.navigate', { url: `${frontend}${route}` })
      await loaded
      await sleep(900)
    }

    async function capture(filename) {
      await evaluate('document.fonts.ready')
      await sleep(350)
      const result = await cdp.send('Page.captureScreenshot', {
        format: 'png',
        fromSurface: true,
        captureBeyondViewport: false,
      })
      await writeFile(path.join(outputDir, filename), Buffer.from(result.data, 'base64'))
    }

    async function setSession(credentials) {
      await evaluate(`sessionStorage.setItem('access_token', ${JSON.stringify(credentials.access)}); sessionStorage.setItem('refresh_token', ${JSON.stringify(credentials.refresh)}); localStorage.setItem('neorx-theme', 'electric');`)
    }

    async function maskClinicalIdentity() {
      await evaluate(`(() => {
        const replacements = new Map([
          ['Juan Sanchez', 'Paciente de prueba'], ['Jose Machaca', 'Paciente de prueba'],
          ['76543321', 'CI anonimizada'], ['1234567', 'CI anonimizada'],
          ['2004-02-11', 'fecha reservada'], ['2000-01-12', 'fecha reservada'],
          ['juan Galindo', 'Paciente de prueba'], ['917865', 'CI anonimizada'],
          ['1999-06-10', 'fecha reservada'], ['60520924', 'teléfono reservado']
        ]);
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        for (const node of nodes) {
          for (const [source, target] of replacements) node.nodeValue = node.nodeValue.replaceAll(source, target);
        }
        for (const row of document.querySelectorAll('tbody tr')) {
          const cells = row.querySelectorAll('td');
          if (cells.length < 5) continue;
          cells[0].textContent = 'Paciente de prueba';
          cells[1].textContent = 'CI anonimizada';
          cells[2].textContent = 'fecha reservada';
          cells[4].textContent = 'teléfono reservado';
        }
      })()`)
    }

    await navigate('/login')
    await capture('03_login.png')

    await navigate('/')
    await evaluate(`document.getElementById('demo')?.scrollIntoView({block:'center'});`)
    await sleep(800)
    await capture('01_categorias.png')
    await evaluate(`Array.from(document.querySelectorAll('*')).find((el) => el.textContent?.trim() === 'Señales dentro de la categoría pleural')?.scrollIntoView({block:'center'});`)
    await capture('02_senales_categoria.png')

    const admin = await token('admin', adminPassword)
    await navigate('/login')
    await setSession(admin)
    await navigate('/dashboard')
    await capture('04_dashboard.png')

    await navigate('/pacientes')
    await evaluate(`Array.from(document.querySelectorAll('button')).find((button) => button.textContent?.includes('Nuevo paciente'))?.click();`)
    await sleep(400)
    await maskClinicalIdentity()
    await capture('05_paciente.png')

    await navigate('/admin/usuarios')
    await capture('10_usuarios.png')

    const doctor = await token('evidencia_documental', doctorPassword)
    await navigate('/login')
    await setSession(doctor)
    await navigate('/escaneo')
    await capture('06_escaneo.png')

    await navigate('/analisis/116')
    await maskClinicalIdentity()
    await evaluate(`document.querySelector('[aria-label="Clasificación por categorías"]')?.scrollIntoView({block:'center'});`)
    await capture('07_analisis.png')

    await navigate('/informes/74')
    await maskClinicalIdentity()
    await capture('08_informe_imagen.png')
    await evaluate(`document.getElementById('hallazgos')?.scrollIntoView({block:'center'});`)
    await sleep(300)
    await capture('09_informe_estructura.png')

    cdp.close()
  } finally {
    chrome.kill()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
