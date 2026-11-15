import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#0b1020", soft: "#141a2e" },
        brand: { DEFAULT: "#6366f1", 600: "#4f46e5" },
      },
    },
  },
  plugins: [],
};
export default config;
