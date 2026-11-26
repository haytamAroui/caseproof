import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function BaseIcon({ size = 16, children, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

/** Minimalist geometric document-and-check mark original to CaseProof. */
export function IconBrandMark({ size = 22, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      <rect x="2" y="2" width="20" height="20" rx="6" fill="currentColor" />
      <path
        d="M7.5 8.5h9M7.5 12h5.5M7.5 15.5h3.5"
        stroke="#ffffff"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M14.2 15.2l1.6 1.6 3.2-3.4"
        stroke="#ffffff"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconFolder(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
    </BaseIcon>
  );
}

export function IconFileCheck(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="m9 15 2 2 4-4" />
    </BaseIcon>
  );
}

export function IconScale(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M12 3v18" />
      <path d="M5 7h14" />
      <path d="M8 21h8" />
      <path d="m5 7-2.5 6a3 3 0 0 0 5 0L5 7Z" />
      <path d="m19 7-2.5 6a3 3 0 0 0 5 0L19 7Z" />
    </BaseIcon>
  );
}

export function IconDownload(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M4 19h16" />
    </BaseIcon>
  );
}

export function IconChevronLeft(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m15 18-6-6 6-6" />
    </BaseIcon>
  );
}

export function IconChevronRight(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m9 18 6-6-6-6" />
    </BaseIcon>
  );
}

export function IconMinus(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M5 12h14" />
    </BaseIcon>
  );
}

export function IconPlus(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M12 5v14M5 12h14" />
    </BaseIcon>
  );
}

export function IconRotateCw(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </BaseIcon>
  );
}

export function IconTone({
  tone,
  size = 13,
}: {
  tone:
    | 'error'
    | 'warning'
    | 'impossible'
    | 'recheck'
    | 'success'
    | 'derived'
    | 'neutral';
  size?: number;
}) {
  if (tone === 'error') {
    return (
      <BaseIcon size={size}>
        <circle cx="12" cy="12" r="9" />
        <path d="m15 9-6 6M9 9l6 6" />
      </BaseIcon>
    );
  }
  if (tone === 'warning') {
    return (
      <BaseIcon size={size}>
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        <path d="M12 9v4M12 17h.01" />
      </BaseIcon>
    );
  }
  if (tone === 'impossible') {
    return (
      <BaseIcon size={size}>
        <circle cx="12" cy="12" r="9" />
        <path d="m5.6 5.6 12.8 12.8" />
      </BaseIcon>
    );
  }
  if (tone === 'recheck') {
    return <IconRotateCw size={size} />;
  }
  if (tone === 'success') {
    return (
      <BaseIcon size={size}>
        <circle cx="12" cy="12" r="9" />
        <path d="m8.5 12.5 2.5 2.5 4.5-5" />
      </BaseIcon>
    );
  }
  if (tone === 'derived') {
    return (
      <BaseIcon size={size}>
        <path d="M12 3 20 12 12 21 4 12 12 3Z" />
      </BaseIcon>
    );
  }
  return (
    <BaseIcon size={size}>
      <circle cx="12" cy="12" r="4" />
    </BaseIcon>
  );
}
