/** Guarda texto con el diálogo nativo del sistema (o descarga si no está disponible). */

export function suggestedGuionFilename(workApplied: string, topicHint?: string): string {
  const fromTopic = (topicHint ?? "")
    .trim()
    .slice(0, 48)
    .replace(/[^\p{L}\p{N}\-_]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  const fromWork = (workApplied.split("/").pop() ?? "guion")
    .replace(/[^\w\-]+/g, "-")
    .replace(/-+/g, "-");
  const base = fromTopic || fromWork || "guion";
  return base.toLowerCase().endsWith(".txt") ? base : `${base}.txt`;
}

export async function saveTextWithPicker(
  text: string,
  suggestedName: string,
): Promise<"saved" | "cancelled" | "fallback"> {
  const body = text.replace(/\r\n/g, "\n");
  const picker = (
    window as Window & {
      showSaveFilePicker?: (opts: {
        suggestedName?: string;
        types?: { description: string; accept: Record<string, string[]> }[];
      }) => Promise<FileSystemFileHandle>;
    }
  ).showSaveFilePicker;

  if (typeof picker === "function") {
    try {
      const handle = await picker({
        suggestedName,
        types: [
          {
            description: "Guion de texto",
            accept: { "text/plain": [".txt", ".md"] },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(body);
      await writable.close();
      return "saved";
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        return "cancelled";
      }
    }
  }

  const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return "fallback";
}
