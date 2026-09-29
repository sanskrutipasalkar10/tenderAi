import type { SelectHTMLAttributes } from "react";

export default function Select({
  className = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-ink-900 focus:border-accent focus:outline-none ${className}`}
      {...rest}
    >
      {children}
    </select>
  );
}
