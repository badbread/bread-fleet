/** @type {import('tailwindcss').Config} */
//
// Same design tokens as the Compliance Troubleshooter. Shared palette
// keeps the portal visually cohesive across modules. If this were a
// monorepo with a shared package, the tokens would live in one place;
// for the MVP, duplication is cheaper than the build complexity.

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        neutral: {
          0: "#FFFFFF",
          50: "#F7F7F5",
          100: "#F1F1EF",
          150: "#E9E9E7",
          200: "#DFDFDC",
          300: "#C9C9C5",
          500: "#787774",
          700: "#37352F",
          800: "#2F2E2B",
          900: "#1F1E1B",
        },
        accent: {
          DEFAULT: "#2383E2",
          subtle: "#E7F3F8",
        },
        severity: {
          low: "#0B6E99",
          "low-bg": "#DDEBF1",
          medium: "#CB912F",
          "medium-bg": "#FBF3DB",
          high: "#D9730D",
          "high-bg": "#FAEBDD",
          critical: "#E03E3E",
          "critical-bg": "#FBE4E4",
        },
        // Chart-specific colors for the trend line and platform bars.
        chart: {
          line: "#2383E2",
          darwin: "#37352F",
          ubuntu: "#D9730D",
          windows: "#2383E2",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        DEFAULT: "3px",
        md: "4px",
        lg: "6px",
        xl: "8px",
      },
      boxShadow: {
        subtle: "0 1px 2px rgba(15, 15, 15, 0.04)",
      },
    },
  },
  plugins: [],
};
