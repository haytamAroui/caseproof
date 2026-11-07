import type { KeyboardEvent, PointerEvent, RefObject } from 'react';

export function clampSplit(value: number, minimum: number, maximum: number) {
  if (!Number.isFinite(value)) return minimum;
  return Math.min(maximum, Math.max(minimum, Math.round(value)));
}

/**
 * Accessible splitter for non-evidentiary pane geometry only. It never changes
 * report content, source hashes, review decisions or persisted user data.
 */
export function SplitHandle({
  containerRef,
  label,
  value,
  min,
  max,
  step,
  unit,
  reset,
  onChange,
  className = '',
}: {
  containerRef: RefObject<HTMLDivElement | null>;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: 'px' | '%';
  reset: number;
  onChange: (next: number) => void;
  className?: string;
}) {
  function update(clientX: number) {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return;
    const valueAtPointer =
      unit === '%'
        ? ((clientX - rect.left) / rect.width) * 100
        : clientX - rect.left;
    onChange(clampSplit(Math.round(valueAtPointer / step) * step, min, max));
  }
  function keyboard(event: KeyboardEvent<HTMLDivElement>) {
    const key = event.key;
    const next =
      key === 'ArrowLeft'
        ? value - step
        : key === 'ArrowRight'
          ? value + step
          : key === 'Home'
            ? min
            : key === 'End'
              ? max
              : null;
    if (next === null) return;
    event.preventDefault();
    onChange(clampSplit(next, min, max));
  }
  function release(event: PointerEvent<HTMLDivElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
  }
  return (
    <div
      className={`cockpit-splitter ${className}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-valuetext={unit === '%' ? `${value} percent` : `${value} pixels`}
      tabIndex={0}
      onKeyDown={keyboard}
      onDoubleClick={() => onChange(reset)}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        update(event.clientX);
      }}
      onPointerMove={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          update(event.clientX);
      }}
      onPointerUp={release}
      onPointerCancel={release}
    />
  );
}
