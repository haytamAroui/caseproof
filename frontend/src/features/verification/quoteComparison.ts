/** Literal navigation over the supplied bounded page text; not verification. */
export function quoteMatches(
  source: string,
  quote: string,
): {
  occurrences: number;
  segments: Array<{ text: string; matched: boolean }>;
} {
  if (!quote || !source)
    return { occurrences: 0, segments: [{ text: source, matched: false }] };
  const positions: number[] = [];
  for (
    let at = source.indexOf(quote);
    at !== -1;
    at = source.indexOf(quote, at + 1)
  ) {
    positions.push(at);
  }
  const segments: Array<{ text: string; matched: boolean }> = [];
  let cursor = 0;
  let index = 0;
  while (index < positions.length) {
    const start = positions[index]!;
    let end = start + quote.length;
    index += 1;
    while (index < positions.length && positions[index]! < end) {
      end = Math.max(end, positions[index]! + quote.length);
      index += 1;
    }
    if (start > cursor)
      segments.push({ text: source.slice(cursor, start), matched: false });
    segments.push({ text: source.slice(start, end), matched: true });
    cursor = end;
  }
  if (cursor < source.length)
    segments.push({ text: source.slice(cursor), matched: false });
  return { occurrences: positions.length, segments };
}
