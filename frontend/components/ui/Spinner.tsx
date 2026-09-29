export default function Spinner({ tone = "light" }: { tone?: "light" | "dark" }) {
  const borderColor = tone === "light" ? "border-white/40 border-t-white" : "border-ink-900/20 border-t-ink-900";
  return <span className={`h-3.5 w-3.5 animate-spin rounded-full border-2 ${borderColor}`} />;
}
