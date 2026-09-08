/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy:      '#0F2942',
        'teal-med': '#0EA5E9',
        success:   '#10B981',
        warning:   '#F59E0B',
        danger:    '#EF4444',
        'scan-bg': '#0A1628',
        surface:   '#132237',
        sidebar:   '#0B1E33',
      },
      fontFamily: {
        heading: ['Outfit', 'sans-serif'],
        body:    ['Nunito', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
}
