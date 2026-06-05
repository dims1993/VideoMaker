import type { Chunk } from "../sceneEditor/types";

export type ImageManifestRow = {
  id: string;
  prompt_id?: string;
  order: number;
  duration_hint_s?: number;
};

export type ImageChunkAudio = {
  chunkId: string;
  audioUrl: string | null;
  narrationText: string;
  durationLabel: string | null;
  hasAudio: boolean;
};

export function chunkIdFromImageRow(img: ImageManifestRow): string {
  const pid = img.prompt_id?.trim();
  return pid || img.id;
}

export function resolveImageChunkAudio(
  work: string,
  img: ImageManifestRow,
  chunkById: Map<string, Chunk>,
): ImageChunkAudio {
  const chunkId = chunkIdFromImageRow(img);
  const chunk = chunkById.get(chunkId);
  const narrationText = (chunk?.narration_text ?? "").trim();

  let audioUrl: string | null = null;
  if (chunk?.audio_url?.trim()) {
    audioUrl = chunk.audio_url;
  } else if (chunk?.status === "done" || narrationText) {
    audioUrl = `/api/audio/chunk-file?work=${encodeURIComponent(work)}&chunk_id=${encodeURIComponent(chunkId)}`;
  }

  const ms =
    chunk?.duration_ms != null && chunk.duration_ms > 0
      ? chunk.duration_ms
      : img.duration_hint_s != null && img.duration_hint_s > 0
        ? img.duration_hint_s * 1000
        : null;
  const durationLabel =
    ms != null && ms > 0 ? `${(ms / 1000).toFixed(1)} s` : null;

  return {
    chunkId,
    audioUrl,
    narrationText,
    durationLabel,
    hasAudio: Boolean(audioUrl),
  };
}

export function buildChunkById(chunks: Chunk[]): Map<string, Chunk> {
  const m = new Map<string, Chunk>();
  for (const c of chunks) m.set(c.id, c);
  return m;
}
