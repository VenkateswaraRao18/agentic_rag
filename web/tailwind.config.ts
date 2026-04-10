import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "#0c0f14",
          raised: "#121722",
          border: "#1e2633",
        },
        accent: {
          DEFAULT: "#3b82f6",
          dim: "#2563eb",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(59,130,246,0.25), 0 20px 50px -20px rgba(0,0,0,0.65)",
      },
    },
  },
  plugins: [],
};

export default config;
