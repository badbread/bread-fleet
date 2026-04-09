/** @type {import('tailwindcss').Config} */
//
// Design tokens. The palette is warm-neutral with a single accent
// blue, intentionally subdued. Borders are very thin and warm rather
// than the cool slate of the default Tailwind palette. Shadows are
// almost absent; the design relies on borders and spacing instead.
//
// The severity colors are pulled from a callout palette that pairs
// a saturated foreground with a pale tinted background, the way a
// well-designed knowledge tool highlights important callouts inline.

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm neutrals. The 50/100/150 levels are background and
        // hover tints; 500 is secondary text; 700 is the primary
        // text color (a warm off-black, not pure #000).
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
        // Single accent. Used sparingly: focus rings, link text,
        // selected items. Primary buttons use neutral-700 instead.
        accent: {
          DEFAULT: "#2383E2",
          subtle: "#E7F3F8",
        },
        // Severity foregrounds + matching pale backgrounds. Each
        // pair forms a callout-style badge.
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
      },
      fontFamily: {
        // Inter as the primary UI font, loaded from Google Fonts
        // in index.html with a system stack fallback for offline.
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
        // Slightly smaller than Tailwind defaults. The design
        // language favors restrained corner radius over playful.
        DEFAULT: "3px",
        md: "4px",
        lg: "6px",
        xl: "8px",
      },
      boxShadow: {
        // Almost nothing. The design uses borders and background
        // tints instead of elevation shadows.
        subtle: "0 1px 2px rgba(15, 15, 15, 0.04)",
      },
    },
  },
  plugins: [],
};
