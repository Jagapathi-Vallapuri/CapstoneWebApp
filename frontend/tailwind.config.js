/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  // Tailwind v4 uses the PostCSS plugin configured in postcss.config.js; no Tailwind plugins here.
  plugins: [],
}