// Applies the saved (or system) theme before first paint, to avoid a flash of the wrong theme.
// Lives in its own file (not inline in index.html) so the Content-Security-Policy can forbid
// inline scripts.
try {
  var saved = localStorage.getItem("orderflow-theme");
  var dark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
} catch (e) {
  /* storage unavailable: fall back to the default theme */
}
