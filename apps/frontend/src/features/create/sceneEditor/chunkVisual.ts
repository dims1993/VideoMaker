import type { Chunk } from "./types";

export function chunkIsPlannable(chunk: Chunk): boolean {
  return Boolean(chunk.narration_text.trim());
}

/** Bloque que puede y necesita prompt visual. */
export function chunkNeedsVisual(chunk: Chunk): boolean {
  if (!chunkIsPlannable(chunk)) return false;
  if (chunk.visual_status === "error" || chunk.visual_status === "planning") return true;
  if (!(chunk.scene_prompt_en ?? "").trim()) return true;
  if (!(chunk.ai_prompt ?? "").trim()) return true;
  return false;
}

export function countPendingVisual(chunks: Chunk[]): number {
  return chunks.filter(chunkNeedsVisual).length;
}
