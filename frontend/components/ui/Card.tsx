import type { MouseEvent, ReactNode } from "react";

const PADDING: Record<"sm" | "md" | "lg", string> = {
  sm: "p-5",
  md: "p-6",
  lg: "p-8",
};

const TONE: Record<"default" | "subtle" | "danger" | "warning" | "dark", string> = {
  default: "border-slate-200 bg-white",
  subtle: "border-slate-100 bg-slate-50",
  danger: "border-severity-high/20 bg-severity-high/5",
  warning: "border-severity-medium/25 bg-severity-medium/5",
  dark: "border-white/10 bg-ink-950",
};

export default function Card({
  padding = "md",
  tone = "default",
  className = "",
  onClick,
  children,
}: {
  padding?: "sm" | "md" | "lg";
  tone?: "default" | "subtle" | "danger" | "warning" | "dark";
  className?: string;
  onClick?: (e: MouseEvent<HTMLDivElement>) => void;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-md border ${TONE[tone]} ${PADDING[padding]} ${className}`} onClick={onClick}>
      {children}
    </div>
  );
}
