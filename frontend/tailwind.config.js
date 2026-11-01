/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: { brand: { 50: '#eef4ff', 100: '#d9e5ff', 200: '#bcd0ff', 500: '#3b6df5', 600: '#2a54d8', 700: '#2243b0', 900: '#16295f' } },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'] },
      boxShadow: { card: '0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08)' }
    }
  },
  plugins: []
}
