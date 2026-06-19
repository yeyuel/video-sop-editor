import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./types/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#192229",
        sand: "#f6efe3",
        pine: "#31584f",
        clay: "#b8694f",
        mist: "#d8e5e0"
      },
      boxShadow: {
        card: "0 18px 50px rgba(25, 34, 41, 0.08)"
      },
      borderRadius: {
        xl2: "1.5rem"
      }
    }
  },
  plugins: []
};

export default config;
