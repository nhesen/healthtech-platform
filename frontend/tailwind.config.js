/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: { colors: { primary: "#1F6FEB", canvas: "#F6F8FC", border: "#D8E0EE" } } },
  plugins: []
};
