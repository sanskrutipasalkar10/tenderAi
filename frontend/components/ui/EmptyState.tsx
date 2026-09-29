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
    <div className="rounded-md border border-dashed border-input bg-card px-6 py-16 text-center">
      {icon && <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-primary">{icon}</div>}
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {actionLabel && actionHref && (
        <div className="mt-6 flex justify-center">
          <Button href={actionHref}>{actionLabel}</Button>
        </div>
      )}
    </div>
  );
}
