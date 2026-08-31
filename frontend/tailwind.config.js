/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#07172d",
          900: "#0f2747",
          800: "#17375e"
        }
      },
      boxShadow: {
        card: "0 1px 3px rgba(15, 39, 71, 0.08), 0 8px 24px rgba(15, 39, 71, 0.06)"
      }
    }
  },
  plugins: []
};

