/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ink: "#172638",
        muted: "#6d7b8d",
        line: "#e5eaf0",
        canvas: "#f5f7fb",
        brand: "#285f58",
        "brand-dark": "#1e4b46",
        mint: "#e6f3ef",
      },
      boxShadow: {
        panel: "0 8px 26px rgba(27, 45, 69, 0.045)",
      },
    },
  },
  plugins: [],
};
