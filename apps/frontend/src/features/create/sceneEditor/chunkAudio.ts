import type { Chunk } from "./types";

/** Bloque narrable que aún necesita TTS (idle, error, o sin audio). */
export function chunkNeedsAudio(chunk: Chunk): boolean {
  if (!chunk.narration_text.trim()) return false;
  if (chunk.status === "error") return true;
  if (chunk.status !== "done") return true;
  if (!chunk.audio_url?.trim()) return true;
  return false;
}

export function countPendingAudio(chunks: Chunk[]): number {
  return chunks.filter(chunkNeedsAudio).length;
}
