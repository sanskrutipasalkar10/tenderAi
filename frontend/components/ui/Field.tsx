import type { ReactNode } from "react";

export default function Field({
  label,
  hint,
  onDark = false,
  children,
}: {
  label: string;
  hint?: string;
  onDark?: boolean;
  children: ReactNode;
}) {
  return (
    <div>
      <label className={`mb-1 block text-sm font-medium ${onDark ? "text-slate-200" : "text-ink-900"}`}>
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}
