"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import Spinner from "./Spinner";

type Variant = "primary" | "dark" | "outline" | "ghost" | "destructive" | "success";
type Size = "xs" | "sm" | "md";

const VARIANT: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400",
  dark: "bg-ink-900 text-white hover:bg-ink-950 disabled:bg-slate-200 disabled:text-slate-400",
  outline:
    "border border-slate-300 bg-white text-ink-900 hover:border-accent hover:text-accent disabled:opacity-50",
  ghost: "text-slate-500 hover:text-ink-900 disabled:opacity-50",
  destructive: "bg-status-no-go text-white hover:bg-red-700 disabled:opacity-50",
  success: "bg-status-go text-white hover:bg-green-700 disabled:opacity-50",
};

// Dark-ground variants (landing hero, login) need a different resting/hover treatment
// than the same variant on a light "paper" background — e.g. `outline` on light paper
// uses a light border, but on ink-950 needs a white-alpha border instead.
const VARIANT_ON_DARK: Partial<Record<Variant, string>> = {
  outline: "border border-white/15 bg-transparent text-slate-100 hover:border-accent-bright hover:text-accent-bright",
  ghost: "text-slate-300 hover:text-white",
};

const SIZE: Record<Size, string> = {
  xs: "px-2.5 py-1 text-xs",
  sm: "px-5 py-2.5 text-sm",
  md: "px-6 py-3 text-sm",
};

type BaseProps = {
  variant?: Variant;
  size?: Size;
  onDark?: boolean;
  loading?: boolean;
  icon?: ReactNode;
  fullWidth?: boolean;
  className?: string;
  children: ReactNode;
};

type ButtonAsButton = BaseProps & {
  href?: undefined;
  type?: "button" | "submit" | "reset";
  onClick?: () => void;
  disabled?: boolean;
  name?: string;
  form?: string;
  "aria-label"?: string;
  tabIndex?: number;
};

type ButtonAsLink = BaseProps & {
  href: string;
};

export default function Button(props: ButtonAsButton | ButtonAsLink) {
  const {
    variant = "primary",
    size = "sm",
    onDark = false,
    loading = false,
    icon,
    fullWidth = false,
    className = "",
    children,
  } = props;

  const styles = `inline-flex items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap transition-colors ${
    (onDark ? VARIANT_ON_DARK[variant] : undefined) ?? VARIANT[variant]
  } ${SIZE[size]} ${fullWidth ? "w-full" : ""} ${className}`;

  if ("href" in props && props.href) {
    return (
      <motion.div
        className={fullWidth ? "w-full" : "inline-block"}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        <Link href={props.href} className={styles}>
          {icon}
          {children}
        </Link>
      </motion.div>
    );
  }

  const buttonProps = props as ButtonAsButton;
  const isDisabled = buttonProps.disabled || loading;

  return (
    <motion.button
      type={buttonProps.type ?? "button"}
      onClick={buttonProps.onClick}
      disabled={isDisabled}
      name={buttonProps.name}
      form={buttonProps.form}
      aria-label={buttonProps["aria-label"]}
      tabIndex={buttonProps.tabIndex}
      whileHover={!isDisabled ? { scale: 1.01 } : undefined}
      whileTap={!isDisabled ? { scale: 0.99 } : undefined}
      className={styles}
    >
      {loading && <Spinner tone={variant === "outline" || variant === "ghost" ? "dark" : "light"} />}
      {!loading && icon}
      {children}
    </motion.button>
  );
}
