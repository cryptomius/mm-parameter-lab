import { useEffect, useRef, useState } from "react";

export type Scale = "linear" | "log10";

interface SliderProps {
  label: string;
  serverValue: number | undefined;
  min: number;
  max: number;
  scale: Scale;
  step?: number;
  format?: (v: number) => string;
  onCommit: (v: number) => Promise<unknown>;
  onHover?: (key: string) => void;
  hoverKey?: string;
  disabled?: boolean;
  unit?: string;
  // For visualisation: when the slider position drives a derived line
  // (e.g. q_target affecting bid/ask), parents can read the live position
  // via this onPreview callback. Most callers don't need this.
  onPreview?: (v: number) => void;
}

const RANGE_STEPS = 200; // resolution of the range track

const toSliderPos = (v: number, min: number, max: number, scale: Scale): number => {
  if (scale === "log10") {
    const lo = Math.log10(min);
    const hi = Math.log10(max);
    const lv = Math.log10(Math.max(min, Math.min(max, v)));
    return ((lv - lo) / (hi - lo)) * RANGE_STEPS;
  }
  return (((Math.max(min, Math.min(max, v)) - min) / (max - min)) * RANGE_STEPS);
};

const fromSliderPos = (pos: number, min: number, max: number, scale: Scale): number => {
  const f = pos / RANGE_STEPS;
  if (scale === "log10") {
    const lo = Math.log10(min);
    const hi = Math.log10(max);
    return Math.pow(10, lo + f * (hi - lo));
  }
  return min + f * (max - min);
};

const defaultFormat = (v: number): string => {
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 100) return v.toFixed(1);
  if (Math.abs(v) >= 1) return v.toFixed(3);
  return v.toFixed(4);
};

export function Slider({
  label,
  serverValue,
  min,
  max,
  scale,
  step,
  format = defaultFormat,
  onCommit,
  onHover,
  hoverKey,
  disabled,
  unit,
  onPreview,
}: SliderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const dirtyRef = useRef(false);
  const [appliedAt, setAppliedAt] = useState<number | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [sliderPos, setSliderPos] = useState<number>(
    serverValue != null ? toSliderPos(serverValue, min, max, scale) : 0,
  );
  const draggingRef = useRef(false);

  // Sync from server when not actively editing
  useEffect(() => {
    if (!dirtyRef.current && !draggingRef.current && serverValue != null) {
      if (inputRef.current) inputRef.current.value = format(serverValue);
      setSliderPos(toSliderPos(serverValue, min, max, scale));
    }
  }, [serverValue, min, max, scale, format]);

  const commitValue = async (v: number) => {
    const clamped = Math.max(min, Math.min(max, v));
    dirtyRef.current = false;
    setIsDirty(false);
    if (clamped === serverValue) return;
    await onCommit(clamped);
    setAppliedAt(Date.now());
  };

  const onTextCommit = () => {
    const raw = inputRef.current?.value ?? "";
    const n = Number(raw);
    if (isNaN(n)) {
      // restore
      if (serverValue != null && inputRef.current)
        inputRef.current.value = format(serverValue);
      dirtyRef.current = false;
      setIsDirty(false);
      return;
    }
    setSliderPos(toSliderPos(n, min, max, scale));
    void commitValue(n);
  };

  const onSliderInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    draggingRef.current = true;
    dirtyRef.current = true;
    setIsDirty(true);
    const pos = Number(e.target.value);
    setSliderPos(pos);
    const v = fromSliderPos(pos, min, max, scale);
    if (inputRef.current) inputRef.current.value = format(v);
    if (onPreview) onPreview(v);
  };

  const onSliderRelease = () => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    const v = fromSliderPos(sliderPos, min, max, scale);
    void commitValue(v);
  };

  const hoverHandlers = onHover && hoverKey
    ? {
        onMouseEnter: () => onHover(hoverKey),
        onFocus: () => onHover(hoverKey),
      }
    : {};

  return (
    <div className="flex items-center gap-2 mb-1.5 text-xs" {...hoverHandlers}>
      <span className="text-sub w-28 truncate flex-shrink-0">{label}</span>
      <input
        ref={inputRef}
        className={`input w-16 flex-shrink-0 ${isDirty ? "ring-1 ring-warn" : ""}`}
        defaultValue={serverValue != null ? format(serverValue) : ""}
        disabled={disabled}
        onChange={() => {
          dirtyRef.current = true;
          setIsDirty(true);
        }}
        onBlur={onTextCommit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
      />
      <input
        type="range"
        className="flex-1 min-w-0 accent-ask"
        min={0}
        max={RANGE_STEPS}
        step={step != null && scale === "linear" ? (step * RANGE_STEPS) / (max - min) : 1}
        value={sliderPos}
        disabled={disabled}
        onChange={onSliderInput}
        onMouseUp={onSliderRelease}
        onTouchEnd={onSliderRelease}
        onKeyUp={onSliderRelease}
      />
      {unit && <span className="text-sub w-6 flex-shrink-0">{unit}</span>}
      {appliedAt != null && (
        <span className="text-[9px] text-ask flex-shrink-0">✓</span>
      )}
    </div>
  );
}
