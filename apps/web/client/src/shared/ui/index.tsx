import type { ButtonHTMLAttributes, ReactNode } from 'react';
export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={props.type ?? 'button'}
      onClick={props.onClick}
      {...props}
      className={`button ${props.className ?? ''}`}
    />
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <p
      className={error ? 'notice error' : 'notice'}
      role={error ? 'alert' : 'status'}
    >
      {children}
    </p>
  );
}
export function StateValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="dimension">
      <dt>{label}</dt>
      <dd>{value.replaceAll('_', ' ')}</dd>
    </div>
  );
}
