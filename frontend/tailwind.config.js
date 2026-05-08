/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#0b0e17", card: "#131722", border: "#1e2336" },
        brand: { DEFAULT: "#2962ff", dim: "#1a3fa8" },
        bull: "#26a69a",
        bear: "#ef5350",
        muted: "#6b7280",
        subtle: "#9ca3af",
      },
      fontFamily: { mono: ["'JetBrains Mono'", "monospace"] },
    },
  },
  plugins: [],
};
