import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0b0d10",
        panel: "#14181d",
        border: "#1f262d",
        ink: "#e7ecf0",
        sub: "#8a96a0",
        bid: "#e34d4d",
        ask: "#46c986",
        warn: "#e6b15e",
      },
      fontFamily: {
        mono: ["ui-monospace", "Menlo", "Consolas", "monospace"],
      },
    },
  },
} satisfies Config;
