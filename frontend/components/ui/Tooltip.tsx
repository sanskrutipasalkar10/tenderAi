"use client";

import { useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

const TOOLTIP_WIDTH = 320;
const VIEWPORT_MARGIN = 12;

/** A small hover tooltip, rendered through a portal into document.body rather than as
 * an absolutely-positioned child of its trigger — this is used inside tables wrapped
 * in Card's overflow-x-auto, and a normal absolute/relative tooltip gets clipped at
 * that container's edge no matter which side it's anchored to, since overflow-x-auto
 * clips both axes. Positioned from the trigger's real screen coordinates instead, and
 * clamped so it never runs off either edge of the viewport. */
export default function Tooltip({
  content,
  children,
  block = false,
}: {
  content: ReactNode;
  children: ReactNode;
  /** The default `inline-block` wrapper shrink-wraps to content width, right for a
   * small trigger like a status badge. A wide trigger (e.g. a full-width row) needs
   * `block` instead, or its flex/width-filling children collapse to content width too. */
  block?: boolean;
}) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const [placement, setPlacement] = useState<{ top: number; left: number; above: boolean } | null>(
    null,
  );

  function show() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    let left = rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2;
    left = Math.max(
      VIEWPORT_MARGIN,
      Math.min(left, window.innerWidth - TOOLTIP_WIDTH - VIEWPORT_MARGIN),
    );
    // Not much room above (e.g. a row near the top of the table) — show it below the
    // trigger instead of letting it run off the top of the viewport.
    const above = rect.top > 160;
    setPlacement({ top: above ? rect.top - 10 : rect.bottom + 10, left, above });
  }

  function hide() {
    setPlacement(null);
  }

  return (
    <span
      ref={triggerRef}
      className={block ? "block w-full" : "inline-block"}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {placement &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            role="tooltip"
            style={{ top: placement.top, left: placement.left, width: TOOLTIP_WIDTH }}
            className={`fixed z-50 rounded-lg border border-border bg-popover px-4 py-3 text-xs leading-relaxed text-foreground shadow-xl ${
              placement.above ? "-translate-y-full" : ""
            }`}
          >
            {content}
          </div>,
          document.body,
        )}
    </span>
  );
}
