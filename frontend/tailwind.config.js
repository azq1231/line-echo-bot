/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  safelist: [
    'bg-red-200',
    'border-red-400',
    'text-red-800',
    'font-semibold',
    // You can add other classes here if they also face purging issues
  ],
}
