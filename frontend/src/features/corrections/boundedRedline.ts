/** A conservative contiguous change, preserving every Unicode code point. */
export function boundedRedline(before: string, after: string) {
  const left = Array.from(before);
  const right = Array.from(after);
  let prefix = 0;
  while (
    prefix < left.length &&
    prefix < right.length &&
    left[prefix] === right[prefix]
  )
    prefix++;
  let suffix = 0;
  while (
    suffix < left.length - prefix &&
    suffix < right.length - prefix &&
    left[left.length - 1 - suffix] === right[right.length - 1 - suffix]
  )
    suffix++;
  return {
    prefix: left.slice(0, prefix).join(''),
    removed: left.slice(prefix, left.length - suffix).join(''),
    added: right.slice(prefix, right.length - suffix).join(''),
    suffix: suffix ? left.slice(left.length - suffix).join('') : '',
  };
}
