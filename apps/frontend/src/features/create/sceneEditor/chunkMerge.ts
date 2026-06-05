import type { Chunk } from "./types";

export function joinNarration(a: string, b: string): string {
  const left = a.trimEnd();
  const right = b.trimStart();
  if (!left) return right;
  if (!right) return left;
  return `${left}\n\n${right}`;
}

/** Fusiona dos bloques; invalida audio y prompts visuales (hay que regenerar). */
export function mergeTwoChunks(keep: Chunk, absorb: Chunk): Chunk {
  return {
    id: keep.id,
    narration_text: joinNarration(keep.narration_text, absorb.narration_text),
    section: keep.section ?? absorb.section ?? null,
    director_note: null,
    audio_url: null,
    duration_ms: null,
    status: "idle",
    visual_status: "idle",
    situation_es: null,
    scene_prompt_en: null,
    ai_prompt: null,
    negative_prompt: null,
  };
}
