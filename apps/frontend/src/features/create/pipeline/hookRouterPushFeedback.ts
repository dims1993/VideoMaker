/** Respuesta de POST /api/pipeline/hook-router/push-to-image-prompts */
export type HookPushToImagePromptsResult = {
  ok?: boolean;
  path?: string;
  prompt_count?: number;
  hybrid?: boolean;
  avatar_count?: number;
  insert_count?: number;
};

export function messageForHookPushToImagePrompts(data: HookPushToImagePromptsResult): string {
  const n = typeof data.prompt_count === "number" ? data.prompt_count : 0;
  const path = (data.path || "pipeline/image_prompts.json").trim();
  if (data.hybrid) {
    const av = typeof data.avatar_count === "number" ? data.avatar_count : 0;
    const ins = typeof data.insert_count === "number" ? data.insert_count : 0;
    return `Volcado correcto: ${n} prompts en ${path} (${av} avatar · ${ins} insert). Abre Image Prompt Writer para revisarlos.`;
  }
  return `Volcado correcto: ${n} prompts (micro-beats) guardados en ${path}. Abre Image Prompt Writer para revisarlos.`;
}
