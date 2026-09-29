import type { InputHTMLAttributes } from "react";

const LIGHT =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-ink-900 focus:border-accent focus:outline-none";
const DARK =
  "w-full rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm text-white outline-none transition-colors focus:border-accent-bright";

export default function Input({
  onDark = false,
  className = "",
  ...rest
}: { onDark?: boolean } & InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${onDark ? DARK : LIGHT} ${className}`} {...rest} />;
}
