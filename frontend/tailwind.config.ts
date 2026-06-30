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
        ink: "#12161C",
        canvas: "#FAFAF8",
        pine: {
          DEFAULT: "#1F4D43",
          dark: "#163832",
          light: "#2A6B5E"
        },
        sand: "#F3F4F2",
        mist: "#E8EDEB",
        clay: "#E07A5F",
        line: "#E8E8E4",
        ai: {
          DEFAULT: "#6366F1",
          soft: "#EEF2FF",
          ring: "#C7D2FE"
        }
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"]
      },
      boxShadow: {
        card: "0 12px 40px rgba(18, 22, 28, 0.06)",
        soft: "0 4px 20px rgba(18, 22, 28, 0.04)",
        lift: "0 12px 32px rgba(31, 77, 67, 0.14)",
        ai: "0 8px 28px rgba(99, 102, 241, 0.18)"
      },
      borderRadius: {
        xl2: "1.25rem"
      },
      animation: {
        "fade-up": "fade-up 420ms ease-out both"
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" }
        }
      }
    }
  },
  plugins: []
};

export default config;
