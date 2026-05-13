import { useCallback, useState } from "react";
import { deleteReq, postJson, putJson } from "../../../services/api";

export type ScriptWriterTemplateListItem = { id: string; name: string };

export type ScriptWriterPacing = "" | "short" | "mixed" | "long";
export type ScriptWriterDataDensity = "" | "low" | "medium" | "high";
export type ScriptWriterStructure = "" | "default_five_blocks" | "four_act";

/**
 * `full_pass` = guion completo (no envía `chunking` al backend).
 * `""` = sin elegir todavía (mismo efecto API que full_pass).
 * Backend: `outline_act1_only` | `sequential_fragments`.
 */
export type ScriptWriterChunking =
  | ""
  | "full_pass"
  | "outline_act1_only"
  | "sequential_fragments";

/** IDs en `narrative_presets.py`; `custom` = pesos solo por caja de texto. */
export type ScriptWriterNarrativePreset = "" | "finanzas" | "entretenimiento" | "tutorial" | "ventas" | "custom";

export function useScriptWriterLibrary() {
  const [scriptWriterTemplates, setScriptWriterTemplates] = useState<ScriptWriterTemplateListItem[]>([]);

  const [scriptWriterTemplateId, setScriptWriterTemplateId] = useState("");
  const [swName, setSwName] = useState("");
  const [swSystem, setSwSystem] = useState("");
  const [swUser, setSwUser] = useState("");
  /** Defaults de sesión que se guardan en el template (para que no “se desvanezcan”). */
  const [swSessionKeywords, setSwSessionKeywords] = useState("");
  const [swSessionContext, setSwSessionContext] = useState("");
  const [swPacing, setSwPacing] = useState<ScriptWriterPacing>("");
  const [swDataDensity, setSwDataDensity] = useState<ScriptWriterDataDensity>("");
  const [swStructure, setSwStructure] = useState<ScriptWriterStructure>("four_act");
  const [swChunking, setSwChunking] = useState<ScriptWriterChunking>("full_pass");
  /** Pesos de minutos por fragmento (misma longitud que la estructura); vacío = defectos del backend. */
  const [swFragmentWeights, setSwFragmentWeights] = useState("");
  const [swNarrativePreset, setSwNarrativePreset] = useState<ScriptWriterNarrativePreset>("");

  const loadScriptWriterTemplates = useCallback(async () => {
    try {
      const r = await fetch("/api/script-writer-templates?limit=200");
      if (!r.ok) return;
      const j = (await r.json()) as { templates: ScriptWriterTemplateListItem[] };
      setScriptWriterTemplates(j.templates ?? []);
    } catch {
      /* ignore */
    }
  }, []);

  const applyTemplateFromApi = useCallback(async (id: string) => {
    if (!id) return;
    const r = await fetch(`/api/script-writer-templates/${encodeURIComponent(id)}`);
    if (!r.ok) return;
    const t = (await r.json()) as {
      name?: string;
      system_instructions?: string;
      user_instructions?: string;
      params_json?: Record<string, unknown>;
    };
    setSwName(t.name || "");
    setSwSystem(t.system_instructions || "");
    setSwUser(t.user_instructions || "");
    const pj = (t.params_json || {}) as {
      pacing?: string;
      data_density?: string;
      structure_preset?: string;
      chunking?: string;
      fragment_minute_weights?: unknown;
      narrative_preset?: string;
      session_keywords?: string;
      session_context?: string;
    };
    setSwSessionKeywords((pj.session_keywords as string) || "");
    setSwSessionContext((pj.session_context as string) || "");
    const p = pj.pacing === "short" || pj.pacing === "mixed" || pj.pacing === "long" ? pj.pacing : "";
    setSwPacing(p);
    const d =
      pj.data_density === "low" || pj.data_density === "medium" || pj.data_density === "high" ? pj.data_density : "";
    setSwDataDensity(d);
    const s =
      pj.structure_preset === "default_five_blocks" || pj.structure_preset === "four_act"
        ? pj.structure_preset
        : "";
    setSwStructure(s);
    const ck = pj.chunking;
    setSwChunking(
      ck === "outline_act1_only"
        ? "outline_act1_only"
        : ck === "sequential_fragments"
          ? "sequential_fragments"
          : "full_pass",
    );
    const fw = pj.fragment_minute_weights;
    if (Array.isArray(fw) && fw.length > 0 && fw.every((x) => typeof x === "number" && !Number.isNaN(x))) {
      setSwFragmentWeights(fw.join(", "));
    } else {
      setSwFragmentWeights("");
    }
    const np = pj.narrative_preset;
    if (np === "finanzas" || np === "entretenimiento" || np === "tutorial" || np === "ventas") {
      setSwNarrativePreset(np);
    } else if (fw && Array.isArray(fw) && fw.length === 4) {
      setSwNarrativePreset("custom");
    } else {
      setSwNarrativePreset("");
    }
  }, []);

  const applyTemplateFields = useCallback((t: {
    name?: string;
    system_instructions?: string;
    user_instructions?: string;
    params_json?: {
      pacing?: string;
      data_density?: string;
      structure_preset?: string;
      chunking?: string;
      narrative_preset?: string;
      fragment_minute_weights?: unknown;
      session_keywords?: string;
      session_context?: string;
    };
  }) => {
    setSwName(t.name || "");
    setSwSystem(t.system_instructions || "");
    setSwUser(t.user_instructions || "");
    const pj = t.params_json ?? {};
    setSwSessionKeywords((pj.session_keywords as string) || "");
    setSwSessionContext((pj.session_context as string) || "");
    const p = pj.pacing === "short" || pj.pacing === "mixed" || pj.pacing === "long" ? pj.pacing : "";
    setSwPacing(p);
    const d = pj.data_density === "low" || pj.data_density === "medium" || pj.data_density === "high" ? pj.data_density : "";
    setSwDataDensity(d);
    const s = pj.structure_preset === "default_five_blocks" || pj.structure_preset === "four_act" ? pj.structure_preset : "";
    setSwStructure(s);
    const ck = pj.chunking;
    setSwChunking(ck === "outline_act1_only" ? "outline_act1_only" : ck === "sequential_fragments" ? "sequential_fragments" : "full_pass");
    const fw = pj.fragment_minute_weights;
    if (Array.isArray(fw) && fw.length > 0 && fw.every((x) => typeof x === "number" && !Number.isNaN(x))) {
      setSwFragmentWeights((fw as number[]).join(", "));
    } else {
      setSwFragmentWeights("");
    }
    const np = pj.narrative_preset;
    if (np === "finanzas" || np === "entretenimiento" || np === "tutorial" || np === "ventas") {
      setSwNarrativePreset(np);
    } else {
      setSwNarrativePreset("");
    }
  }, []);

  const buildPayload = useCallback(() => {
    const params_json: Record<string, unknown> = {};
    if (swSessionKeywords.trim()) params_json.session_keywords = swSessionKeywords.trim();
    if (swSessionContext.trim()) params_json.session_context = swSessionContext.trim();
    if (swPacing) params_json.pacing = swPacing;
    if (swDataDensity) params_json.data_density = swDataDensity;
    if (swStructure) params_json.structure_preset = swStructure;
    if (swStructure === "four_act" && swNarrativePreset && swNarrativePreset !== "custom") {
      params_json.narrative_preset = swNarrativePreset;
    }
    if (swChunking === "outline_act1_only") params_json.chunking = "outline_act1_only";
    if (swChunking === "sequential_fragments") params_json.chunking = "sequential_fragments";
    if (swChunking === "sequential_fragments" && swFragmentWeights.trim()) {
      const parts = swFragmentWeights
        .split(/[,;\n]+/)
        .map((x) => x.trim())
        .filter(Boolean)
        .map(Number);
      if (parts.length > 0 && parts.every((x) => !Number.isNaN(x))) {
        params_json.fragment_minute_weights = parts;
      }
    }
    return {
      name: swName,
      system_instructions: swSystem,
      user_instructions: swUser,
      params_json,
    };
  }, [swName, swSystem, swUser, swSessionKeywords, swSessionContext, swPacing, swDataDensity, swStructure, swChunking, swFragmentWeights, swNarrativePreset]);

  const saveTemplate = useCallback(async () => {
    const payload = buildPayload();
    if (scriptWriterTemplateId) {
      await putJson(`/api/script-writer-templates/${encodeURIComponent(scriptWriterTemplateId)}`, payload);
    } else {
      const res = await postJson<{ template?: { id: string } }>(`/api/script-writer-templates`, payload);
      const id = res?.template?.id;
      if (id) setScriptWriterTemplateId(id);
    }
    await loadScriptWriterTemplates();
  }, [buildPayload, scriptWriterTemplateId, loadScriptWriterTemplates]);

  const deleteTemplate = useCallback(async () => {
    if (!scriptWriterTemplateId) return;
    await deleteReq(`/api/script-writer-templates/${encodeURIComponent(scriptWriterTemplateId)}`);
    setScriptWriterTemplateId("");
    await loadScriptWriterTemplates();
  }, [scriptWriterTemplateId, loadScriptWriterTemplates]);

  return {
    scriptWriterTemplates,
    loadScriptWriterTemplates,
    scriptWriterTemplateId,
    setScriptWriterTemplateId,
    swName,
    setSwName,
    swSystem,
    setSwSystem,
    swUser,
    setSwUser,
    swSessionKeywords,
    setSwSessionKeywords,
    swSessionContext,
    setSwSessionContext,
    swPacing,
    setSwPacing,
    swDataDensity,
    setSwDataDensity,
    swStructure,
    setSwStructure,
    swChunking,
    setSwChunking,
    swFragmentWeights,
    setSwFragmentWeights,
    swNarrativePreset,
    setSwNarrativePreset,
    applyTemplateFromApi,
    applyTemplateFields,
    saveTemplate,
    deleteTemplate,
  };
}

export type ScriptWriterLibraryStore = ReturnType<typeof useScriptWriterLibrary>;
