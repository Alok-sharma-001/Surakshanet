/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#FFF7ED',
          100: '#FFEDD5',
          200: '#FED7AA',
          300: '#FDBA74',
          400: '#FB923C',
          500: '#F97316',
          600: '#EA580C',
          700: '#C2410C',
          800: '#9A3412',
          DEFAULT: '#EA580C',
        },
        surface: {
          primary: '#FFFFFF',
          secondary: '#FAF8F6',
          card: '#FFFFFF',
          border: '#EFE9E5',
          muted: '#8A7A78',
        },
        studio: {
          bg: '#F5DDD8',
          bgLight: '#FDF0ED',
          bgDark: '#ECCBC4',
          coral: '#E5584D',
          coralLight: '#F3796F',
          coralDark: '#B9362C',
          pink: '#F7C6BF',
          card: '#FFFFFF',
          black: '#0D0E11',
          text: '#221E1E',
          muted: '#8A7A78',
        },
      },
      fontFamily: {
        syne: ['Syne', 'sans-serif'],
        grotesk: ['"Space Grotesk"', 'sans-serif'],
        sans: ['"Space Grotesk"', 'Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'orb': '0 25px 50px -12px rgba(0, 0, 0, 0.4), inset 0 2px 4px rgba(255, 255, 255, 0.6)',
        'studio-card': '0 20px 40px -15px rgba(234, 88, 12, 0.08), 0 0 1px rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [],
}
