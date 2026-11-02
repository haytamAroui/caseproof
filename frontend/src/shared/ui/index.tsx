import { useEffect, useRef, useState } from 'react';
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

/** Guard ephemeral form work; session loss still clears it immediately. */
export function UnsavedChanges({ dirty }: { dirty: boolean }) {
  const [destination, setDestination] = useState<HTMLAnchorElement | null>(
    null,
  );
  const dialog = useRef<HTMLDialogElement>(null),
    bypass = useRef(false);
  useEffect(() => {
    if (!dirty) return;
    function leave(event: MouseEvent) {
      if (
        bypass.current ||
        event.defaultPrevented ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey ||
        event.button !== 0
      )
        return;
      const anchor =
        event.target instanceof Element
          ? event.target.closest('a[href]')
          : null;
      if (
        !(anchor instanceof HTMLAnchorElement) ||
        anchor.target ||
        anchor.download ||
        anchor.origin !== location.origin ||
        (anchor.pathname === location.pathname &&
          anchor.search === location.search)
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      setDestination(anchor);
    }
    function unload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    document.addEventListener('click', leave, true);
    window.addEventListener('beforeunload', unload);
    return () => {
      document.removeEventListener('click', leave, true);
      window.removeEventListener('beforeunload', unload);
    };
  }, [dirty]);
  useEffect(() => {
    if (destination && dirty) dialog.current?.showModal();
    else dialog.current?.close();
  }, [destination, dirty]);
  return (
    <dialog
      ref={dialog}
      aria-labelledby="leave-title"
      aria-describedby="leave-description"
      onCancel={(event) => {
        event.preventDefault();
        setDestination(null);
      }}
    >
      <h2 id="leave-title">Leave unsaved work?</h2>
      <p id="leave-description">
        Form values and selected files will be cleared. A stopped remote
        operation may already have committed; reopen its current state to
        reconcile.
      </p>
      <div className="catalog-actions">
        <Button
          autoFocus
          onClick={() => {
            destination?.focus();
            setDestination(null);
          }}
        >
          Stay here
        </Button>
        <Button
          onClick={() => {
            const anchor = destination;
            setDestination(null);
            dialog.current?.close();
            bypass.current = true;
            anchor?.click();
            bypass.current = false;
          }}
        >
          Leave and discard form
        </Button>
      </div>
    </dialog>
  );
}
