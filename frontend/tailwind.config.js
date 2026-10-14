/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        void: "#131316",
        fog: "#f7f7f8",
        pureWhite: "#ffffff",
        graphite: "#5e5f6e",
        ash: "#747686",
        hairline: "#d9d9de",
        mist: "#eeeef0",
        stone: "#9394a1",
        obsidian: "#212126",
        darkSurface: "#2f3037",
        slateMid: "#696a78",
        violet: {
          DEFAULT: "#6c47ff",
          soft: "#615cf6",
          subtle: "rgba(108, 71, 255, 0.08)",
          border: "rgba(108, 71, 255, 0.25)",
        },
        cyanSpark: "#5de3ff",
        status: {
          normal: "#5e5f6e",
          moderate: "#6c47ff",
          high: "#e5484d",
          critical: "#d32f2f",
          unconfirmed: "#d97706",
          success: "#16a34a",
        },
      },
      fontFamily: {
        sans: ["Geist", "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        ui: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["'Söhne Mono'", "'JetBrains Mono'", "monospace"],
      },
      borderRadius: {
        button: "6px",
        input: "6px",
        cardSm: "8px",
        card: "16px",
      },
      boxShadow: {
        subtle: "0 1px 3px rgba(19, 19, 22, 0.05), 0 1px 2px rgba(19, 19, 22, 0.03)",
        card: "0 2px 8px -2px rgba(19, 19, 22, 0.06), 0 1px 4px -1px rgba(19, 19, 22, 0.04)",
        obsidian: "0 4px 20px -2px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)",
      },
    },
  },
  plugins: [],
};
