import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const css = fs.readFileSync(path.join(here, '../src/index.css'), 'utf8')
const themes = ['clinical', 'hospital', 'wellness', 'diagnostic', 'dark', 'electric', 'graphite']
const tokens = Object.fromEntries(themes.map((theme) => [theme, {}]))
const blocks = /html\[data-theme="([^"]+)"\]\s*\{([\s\S]*?)\}/g

for (const match of css.matchAll(blocks)) {
  const [, theme, body] = match
  if (!tokens[theme]) continue
  for (const variable of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    tokens[theme][variable[1]] = variable[2]
  }
}

function luminance(hex) {
  const rgb = hex.slice(1).match(/.{2}/g).map((value) => Number.parseInt(value, 16) / 255)
    .map((value) => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
  return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
}

function contrast(first, second) {
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a)
  return (light + .05) / (dark + .05)
}

const checks = [
  ['text-main', 'surface-solid', 7, 'texto principal'],
  ['button-text', 'button-bg', 4.5, 'botón primario'],
  ['link-color', 'surface-solid', 4.5, 'enlace'],
  ['highlight-text', 'highlight', 4.5, 'resaltado'],
]
let failed = false

for (const theme of themes) {
  const results = checks.map(([foreground, background, minimum, label]) => {
    const fg = tokens[theme][foreground]
    const bg = tokens[theme][background]
    if (!fg || !bg) throw new Error(`${theme}: falta --${foreground} o --${background}`)
    const ratio = contrast(fg, bg)
    if (ratio < minimum) failed = true
    return `${label} ${ratio.toFixed(2)}:1${ratio >= minimum ? ' ✓' : ` ✗ (mínimo ${minimum}:1)`}`
  })
  console.log(`${theme}: ${results.join(' · ')}`)
}

if (failed) process.exitCode = 1