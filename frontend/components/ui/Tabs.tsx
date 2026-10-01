import type { ComponentType, ReactNode } from "react";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon?: ReactNode;
}

// A small colored icon chip for tab/subtab labels and factor rows — reuses this
// project's existing semantic tokens (no new colors invented) so "give tabs an icon"
// stays visually consistent with the severity/status badges already used everywhere
// else, rather than introducing an arbitrary rainbow.
const CHIP_TONE = {
  primary: "bg-accent text-primary",
  go: "bg-status-go/10 text-status-go",
  warning: "bg-severity-medium/10 text-severity-medium",
  danger: "bg-severity-high/10 text-severity-high",
} as const;

export function TabIconChip({
  icon: Icon,
  tone = "primary",
}: {
  icon: ComponentType<{ className?: string }>;
  tone?: keyof typeof CHIP_TONE;
}) {
  return (
    <span
      className={`inline-flex h-5 w-5 flex-none items-center justify-center rounded-full ${CHIP_TONE[tone]}`}
    >
      <Icon className="h-3 w-3" />
    </span>
  );
}

export default function Tabs<T extends string>({
  items,
  active,
  onChange,
  size = "md",
}: {
  items: readonly TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
  size?: "sm" | "md";
}) {
  const padding = size === "sm" ? "px-3 py-2" : "px-4 py-2.5";
  return (
    <div className="flex flex-wrap gap-1 border-b border-border">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={`-mb-px inline-flex items-center gap-1.5 border-b-2 text-sm font-medium transition-colors ${padding} ${
            active === item.id
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </div>
  );
}
