import type { SelectHTMLAttributes } from "react";

export default function Select({
  className = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none ${className}`}
      {...rest}
    >
      {children}
    </select>
  );
}
