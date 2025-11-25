/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Dark theme colors
        dark: {
          bg: '#0d1117',
          card: '#161b22',
          border: '#30363d',
          hover: '#21262d',
        },
        // Accent colors
        accent: {
          green: '#3fb950',
          red: '#f85149',
          yellow: '#d29922',
          blue: '#58a6ff',
        }
      },
    },
  },
  plugins: [],
}
