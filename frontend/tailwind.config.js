/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#EC5E2D",
        secondary: "#D9785A",
        background: "#FAF6ED",
        surface: "#E9D8C3",
        neutral: "#D1B38F",
        text: "#2C2520",
        "secondary-text": "#6F5A4B",
        accent: "#596044"
      },
      fontFamily: {
        sans: ['Satoshi', 'sans-serif'],
        serif: ['Fraunces', 'serif'],
        logo: ['Borel', 'cursive'],
      }
    },
  },
  plugins: [],
}
