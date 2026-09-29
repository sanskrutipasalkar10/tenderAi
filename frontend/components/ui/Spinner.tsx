export default function Spinner({ tone = "light" }: { tone?: "light" | "dark" }) {
  const borderColor = tone === "light" ? "border-white/40 border-t-white" : "border-foreground/20 border-t-foreground";
  return <span className={`h-3.5 w-3.5 animate-spin rounded-full border-2 ${borderColor}`} />;
}
