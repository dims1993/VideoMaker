/** Texto listo para pegar en la descripción de YouTube (cuerpo + capítulos + hashtags). */

export type YoutubeDescriptionBuild = {
  text: string;
  warnings: string[];
  hasDescription: boolean;
  chapterCount: number;
  tagCount: number;
};

type ChapterRow = { label: string; start_seconds: number };

export function formatChapterTimestamp(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function parseChapters(platform: Record<string, unknown>): ChapterRow[] {
  const raw = platform.chapters_suggestion;
  if (!Array.isArray(raw)) return [];
  const rows: ChapterRow[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    const label = String(o.label ?? o.title ?? "").trim();
    if (!label) continue;
    let start = 0;
    const sec = o.start_seconds;
    if (typeof sec === "number" && Number.isFinite(sec)) {
      start = Math.max(0, Math.round(sec));
    } else if (typeof sec === "string" && sec.trim()) {
      const n = Number(sec);
      if (Number.isFinite(n)) start = Math.max(0, Math.round(n));
    }
    rows.push({ label, start_seconds: start });
  }
  rows.sort((a, b) => a.start_seconds - b.start_seconds);
  return rows;
}

/** Hashtag sin espacios (YouTube no admite espacios en hashtags). */
export function tagToHashtag(tag: string): string {
  const core = tag.replace(/^#+/, "").trim();
  if (!core) return "";
  const slug = core
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[^\w]+/g, "")
    .slice(0, 80);
  if (!slug) return "";
  return `#${slug}`;
}

function parseTags(platform: Record<string, unknown>): string[] {
  const raw = platform.tags;
  if (!Array.isArray(raw)) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const item of raw) {
    const t = String(item ?? "").trim();
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

function formatTagsBlock(tags: string[]): string {
  const hashtags = tags.map(tagToHashtag).filter(Boolean);
  if (!hashtags.length) return "";
  return hashtags.join(" ");
}

export function buildYoutubeDescriptionFromMetadata(
  metadata: unknown,
): YoutubeDescriptionBuild {
  const warnings: string[] = [];
  if (!metadata || typeof metadata !== "object") {
    return {
      text: "",
      warnings: ["metadata vacío o inválido"],
      hasDescription: false,
      chapterCount: 0,
      tagCount: 0,
    };
  }
  const root = metadata as Record<string, unknown>;
  const platform =
    root.platform && typeof root.platform === "object"
      ? (root.platform as Record<string, unknown>)
      : {};

  const description = String(platform.description ?? "").trim();
  const chapters = parseChapters(platform);
  const tags = parseTags(platform);
  const tagsBlock = formatTagsBlock(tags);

  const hasContent = Boolean(description || chapters.length || tagsBlock);
  if (!hasContent) {
    warnings.push(
      "Falta platform.description, chapters_suggestion y platform.tags.",
    );
  } else {
    if (!description) warnings.push("Sin platform.description.");
    if (chapters.length === 0) warnings.push("Sin chapters_suggestion.");
    if (!tagsBlock) warnings.push("Sin platform.tags (o no se pudieron convertir a hashtags).");
  }

  const parts: string[] = [];
  if (description) parts.push(description);

  if (chapters.length > 0) {
    const lines = chapters.map(
      (ch) => `${formatChapterTimestamp(ch.start_seconds)} ${ch.label}`,
    );
    parts.push(lines.join("\n"));
  }

  if (tagsBlock) parts.push(tagsBlock);

  return {
    text: parts.join("\n\n"),
    warnings: hasContent
      ? warnings.filter(
          (w) =>
            !w.startsWith("Sin platform.description.") &&
            !w.startsWith("Sin chapters_suggestion.") &&
            !w.startsWith("Sin platform.tags"),
        )
      : warnings,
    hasDescription: Boolean(description),
    chapterCount: chapters.length,
    tagCount: tags.length,
  };
}

export function parseMetadataForYoutube(jsonText: string): {
  metadata: Record<string, unknown> | null;
  parseError: string | null;
} {
  const trimmed = jsonText.trim();
  if (!trimmed) {
    return { metadata: null, parseError: "JSON vacío" };
  }
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { metadata: null, parseError: "El JSON debe ser un objeto" };
    }
    return { metadata: parsed as Record<string, unknown>, parseError: null };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "JSON inválido";
    return { metadata: null, parseError: msg };
  }
}
