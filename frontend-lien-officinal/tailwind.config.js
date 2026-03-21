/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  theme: {
    extend: {
      keyframes: {
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '20%': { transform: 'translateX(-6px)' },
          '40%': { transform: 'translateX(6px)' },
          '60%': { transform: 'translateX(-4px)' },
          '80%': { transform: 'translateX(4px)' },
        },
      },
      animation: {
        shake: 'shake 0.5s ease-in-out',
      },
    },
  },
  safelist: [
    // Couleurs dynamiques des avatars collaborateurs
    { pattern: /bg-(blue|indigo|purple|pink|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|violet|fuchsia|rose|slate|gray|stone)-500/ },
  ],
  plugins: [],
}