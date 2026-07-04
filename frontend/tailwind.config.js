/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12151C",        // page background
        surface: "#1B212C",    // dark card / sidebar
        surfaceLight: "#242C3A",
        paper: "#FCFAF6",      // light content card (transcript, quiz)
        border: "#2C3444",
        muted: "#8B93A6",      // secondary text on dark
        mutedPaper: "#6B7280", // secondary text on paper
        signal: "#E8A33D",     // amber accent — "the signal captured"
        signalDim: "#B87F2E",
        student: "#7C7AFF",    // indigo — student branch
        team: "#3FA79A",       // teal — professional branch
      },
      fontFamily: {
        display: ["var(--font-space-grotesk)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-plex-mono)", "monospace"],
      },
      borderRadius: {
        card: "14px",
      },
    },
  },
  plugins: [],
};
