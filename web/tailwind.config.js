/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
      colors: {
        ink: "#111827",
        muted: "#6b7280",
        border: "#e5e7eb",
        bg: "#f8f7f4",
        surface: "#ffffff",
        accent: "#111827",
        accentDark: "#0b0f17",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};
