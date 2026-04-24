import { useEffect, useState, useRef } from "react";

/**
 * MovingNumber is a premium counter component that interpolates between values.
 * Hardened for reliability: ensures consistent start/end points even on fast data flips.
 */
export function MovingNumber({ value, prefix = "", suffix = "", duration = 800, decimals = 0 }: { value: number, prefix?: string, suffix?: string, duration?: number, decimals?: number }) {
  const [displayValue, setDisplayValue] = useState(0);
  const prevValueRef = useRef(0);
  const requestRef = useRef<number>();
  const startTimeRef = useRef<number>();

  useEffect(() => {
    // Reset animation state for the new value change
    startTimeRef.current = undefined;
    const startVal = prevValueRef.current;
    const endVal = value;

    if (startVal === endVal) return;

    const animate = (time: number) => {
      if (startTimeRef.current === undefined) {
        startTimeRef.current = time;
      }
      
      const elapsed = time - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      
      // Clinical Ease Out: 1 - (1 - x)^4
      const ease = 1 - Math.pow(1 - progress, 4);
      const current = startVal + (endVal - startVal) * ease;
      
      setDisplayValue(current);

      if (progress < 1) {
        requestRef.current = requestAnimationFrame(animate);
      } else {
        prevValueRef.current = endVal;
      }
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [value, duration]);

  return (
    <span className="mg-moving-number" style={{ fontVariantNumeric: "tabular-nums" }}>
      {prefix}{displayValue.toFixed(decimals)}{suffix}
    </span>
  );
}
