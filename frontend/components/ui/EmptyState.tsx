import type { ReactNode } from "react";
import Button from "./Button";

export default function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionHref,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      {icon && <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-accent">{icon}</div>}
      <p className="text-sm font-medium text-ink-900">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">{description}</p>
      {actionLabel && actionHref && (
        <div className="mt-6 flex justify-center">
          <Button href={actionHref}>{actionLabel}</Button>
        </div>
      )}
    </div>
  );
}
