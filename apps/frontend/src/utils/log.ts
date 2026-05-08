export type ParsedLogEntry = { time: string; step: string; detail: string; raw: string };

export function parseLogTail(text: string): ParsedLogEntry[] {
  const out: ParsedLogEntry[] = [];
  for (const raw of text.split("\n")) {
    if (!raw.trim()) continue;
    const m = raw.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$/);
    if (m) {
      out.push({ time: m[1], step: m[2].trim(), detail: m[3].trim(), raw });
    } else {
      out.push({ time: "", step: "otro", detail: raw.trim(), raw });
    }
  }
  return out;
}

