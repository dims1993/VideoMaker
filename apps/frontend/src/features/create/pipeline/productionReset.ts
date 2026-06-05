import { postJson } from "../../../services/api";

export type ProductionResetScope =
  | "scene_editor_visual"
  | "image_prompts"
  | "voiceovers"
  | "images_generation";

export type ProductionResetResult = {
  ok?: boolean;
  scope?: string;
  cleared?: string[];
  chunks_updated?: number;
  detail?: string;
};

const CONFIRM: Record<ProductionResetScope, string> = {
  scene_editor_visual:
    "Se borrarán los prompts visuales de todos los bloques (planificar / exportar visual).\n\n" +
    "Se conservan el texto narrable y el audio ya generado.\n\n¿Continuar?",
  image_prompts:
    "Se borrará pipeline/image_prompts.json y el manifest de Images Generation (PNG incluidos).\n\n" +
    "Hook/Body routers y el guion no se tocan. Podrás volver a ejecutar IPW Start o importar de nuevo.\n\n¿Continuar?",
  voiceovers:
    "Se reinicia la producción de voiceovers en esta sesión:\n" +
    "· prompts visuales y audio por bloque\n" +
    "· scene_audio/ y narracion.wav (historial incluido)\n" +
    "· image_prompts.json solo si vino del export Visual legacy\n\n" +
    "Los bloques de texto del Scene Editor se conservan.\n\n¿Continuar?",
  images_generation:
    "Se borrará el manifest de imágenes, los PNG en pipeline/images/ y cualquier cola Gemini Web activa.\n\n" +
    "image_prompts.json no se modifica (re-envía desde IPW si necesitas otro manifest).\n\n¿Continuar?",
};

export async function runProductionReset(
  work: string,
  scope: ProductionResetScope,
): Promise<ProductionResetResult | null> {
  if (!window.confirm(CONFIRM[scope])) return null;
  return postJson<ProductionResetResult>("/api/pipeline/production-reset", {
    work,
    scope,
  });
}

export function formatProductionResetMessage(res: ProductionResetResult): string {
  const items = res.cleared ?? [];
  if (items.length === 0) {
    return "Listo. No había artefactos que borrar (o ya estaban vacíos).";
  }
  const head =
    res.chunks_updated != null && res.chunks_updated > 0
      ? `${res.chunks_updated} bloque(s) actualizado(s). `
      : "";
  const shown = items.length <= 4 ? items.join(", ") : `${items.slice(0, 4).join(", ")} (+${items.length - 4})`;
  return `${head}Eliminado: ${shown}.`;
}
