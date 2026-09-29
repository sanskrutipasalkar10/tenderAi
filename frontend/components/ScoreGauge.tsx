"use client";

import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useState } from "react";

const SIZE = 160;
const STROKE = 10;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** A circular 0-100 score gauge — used for the Go/No-Go score and the Risk Finder's
 * overall risk score. Pure presentation: the score and its color bucket are always
 * computed upstream from real backend data, never invented here. The arc draws in and
 * the number counts up on mount/score-change — motion, not new information. */
export default function ScoreGauge({
  score,
  label,
  colorClass,
}: {
  score: number;
  label: string;
  colorClass: string;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  const targetOffset = CIRCUMFERENCE - (clamped / 100) * CIRCUMFERENCE;
  const [display, setDisplay] = useState(0);
  const strokeDashoffset = useMotionValue(CIRCUMFERENCE);
  const roundedOffset = useTransform(strokeDashoffset, (v) => v);

  useEffect(() => {
    const numberControls = animate(0, clamped, {
      duration: 1.1,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    const arcControls = animate(strokeDashoffset, targetOffset, {
      duration: 1.1,
      ease: "easeOut",
    });
    return () => {
      numberControls.stop();
      arcControls.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-run only when the score itself changes
  }, [clamped, targetOffset]);

  return (
    <div className="inline-flex flex-col items-center">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} className="-rotate-90">
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            strokeWidth={STROKE}
            fill="none"
            className="stroke-border"
          />
          <motion.circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            strokeWidth={STROKE}
            fill="none"
            strokeDasharray={CIRCUMFERENCE}
            style={{ strokeDashoffset: roundedOffset }}
            strokeLinecap="round"
            className={colorClass}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="data-mono text-3xl font-semibold text-foreground">{display}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </div>
      </div>
      <span className="mt-3 text-sm font-medium text-muted-foreground">{label}</span>
    </div>
  );
}
