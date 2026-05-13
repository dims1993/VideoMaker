import { useCallback, useState } from "react";
import { deleteReq, postJson, putJson } from "../../../services/api";

export type PromptTemplateListItem = { id: string; name: string };

export function usePromptLibrary() {
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplateListItem[]>([]);

  const [promptTemplateId, setPromptTemplateId] = useState("");
  const [promptName, setPromptName] = useState("");
  const [promptHookStyle, setPromptHookStyle] = useState("");
  const [promptVisualStyle, setPromptVisualStyle] = useState("");
  const [promptTone, setPromptTone] = useState("");
  const [promptSystem, setPromptSystem] = useState("");
  const [promptUser, setPromptUser] = useState("");
  const [promptTopic, setPromptTopic] = useState("");
  const [promptTargetAudience, setPromptTargetAudience] = useState("");
  const [promptLangCode, setPromptLangCode] = useState("es-ES");
  const [promptSlangLevel, setPromptSlangLevel] = useState<"low" | "medium" | "high">("low");
  const [promptNarrTone, setPromptNarrTone] = useState("");
  const [promptHookType, setPromptHookType] = useState("");
  const [promptCtaType, setPromptCtaType] = useState("");
  const [promptAspectRatio, setPromptAspectRatio] = useState("9:16");
  const [promptVisualStyle2, setPromptVisualStyle2] = useState("");
  const [promptKeyPoints, setPromptKeyPoints] = useState("");

  const loadPromptTemplates = useCallback(async () => {
    try {
      const r = await fetch("/api/prompt-templates?limit=200");
      if (!r.ok) return;
      const j = (await r.json()) as { templates: PromptTemplateListItem[] };
      setPromptTemplates(j.templates ?? []);
    } catch {
      /* ignore */
    }
  }, []);

  const buildPayload = useCallback(() => {
    return {
      name: promptName,
      hook_style: promptHookStyle,
      visual_style: promptVisualStyle,
      tone: promptTone,
      system_instructions: promptSystem,
      user_instructions: promptUser,
      params_json: {
        target_audience: promptTargetAudience,
        language_context: { code: promptLangCode, slang_level: promptSlangLevel },
        narrative_structure: {
          tone: promptNarrTone,
          hook_type: promptHookType,
          cta_type: promptCtaType,
        },
        visual_identity: { style: promptVisualStyle2, aspect_ratio: promptAspectRatio },
        key_points: promptKeyPoints
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
      },
    };
  }, [
    promptName,
    promptHookStyle,
    promptVisualStyle,
    promptTone,
    promptSystem,
    promptUser,
    promptTargetAudience,
    promptLangCode,
    promptSlangLevel,
    promptNarrTone,
    promptHookType,
    promptCtaType,
    promptAspectRatio,
    promptVisualStyle2,
    promptKeyPoints,
  ]);

  const saveTemplate = useCallback(async (): Promise<string> => {
    const base = buildPayload();
    const nameForApi =
      (base.name || "").trim() || (promptTopic || "").trim() || "Plantilla sin nombre";
    const payload = { ...base, name: nameForApi };
    if (promptTemplateId) {
      await putJson(`/api/prompt-templates/${encodeURIComponent(promptTemplateId)}`, payload);
      await loadPromptTemplates();
      return promptTemplateId;
    } else {
      const res = await postJson<{ ok?: boolean; template?: { id?: string | number } }>(`/api/prompt-templates`, payload);
      const rawId = res?.template?.id;
      const id = rawId != null && rawId !== "" ? String(rawId) : "";
      if (id) {
        setPromptTemplateId(id);
        if (!(promptName || "").trim() && (promptTopic || "").trim()) {
          setPromptName(nameForApi);
        }
      }
      await loadPromptTemplates();
      return id;
    }
  }, [buildPayload, promptTemplateId, loadPromptTemplates, promptName, promptTopic]);

  const clearTemplate = useCallback(() => {
    setPromptTemplateId("");
    setPromptName("");
    setPromptHookStyle("");
    setPromptVisualStyle("");
    setPromptTone("");
    setPromptSystem("");
    setPromptUser("");
    setPromptTopic("");
    setPromptTargetAudience("");
    setPromptLangCode("es-ES");
    setPromptSlangLevel("low");
    setPromptNarrTone("");
    setPromptHookType("");
    setPromptCtaType("");
    setPromptAspectRatio("9:16");
    setPromptVisualStyle2("");
    setPromptKeyPoints("");
  }, []);

  const applyTemplateFields = useCallback((t: {
    name?: string;
    hook_style?: string;
    visual_style?: string;
    tone?: string;
    system_instructions?: string;
    user_instructions?: string;
    params_json?: Record<string, unknown>;
  }) => {
    setPromptName(t.name || "");
    setPromptHookStyle(t.hook_style || "");
    setPromptVisualStyle(t.visual_style || "");
    setPromptTone(t.tone || "");
    setPromptSystem(t.system_instructions || "");
    setPromptUser(t.user_instructions || "");
    const pj = (t.params_json || {}) as {
      target_audience?: string;
      language_context?: { code?: string; slang_level?: string };
      narrative_structure?: { tone?: string; hook_type?: string; cta_type?: string };
      visual_identity?: { style?: string; aspect_ratio?: string };
      key_points?: string[];
    };
    setPromptTargetAudience(pj.target_audience || "");
    setPromptLangCode(pj.language_context?.code || "es-ES");
    const sl = pj.language_context?.slang_level;
    setPromptSlangLevel(sl === "medium" || sl === "high" ? sl : "low");
    setPromptNarrTone(pj.narrative_structure?.tone || "");
    setPromptHookType(pj.narrative_structure?.hook_type || "");
    setPromptCtaType(pj.narrative_structure?.cta_type || "");
    setPromptAspectRatio(pj.visual_identity?.aspect_ratio || "9:16");
    setPromptVisualStyle2(pj.visual_identity?.style || "");
    setPromptKeyPoints(Array.isArray(pj.key_points) ? pj.key_points.join(", ") : "");
  }, []);

  const applyTemplateFromApi = useCallback(async (id: string) => {
    if (!id) return;
    const r = await fetch(`/api/prompt-templates/${encodeURIComponent(id)}`);
    if (!r.ok) return;
    const t = await r.json() as Parameters<typeof applyTemplateFields>[0];
    applyTemplateFields(t);
  }, [applyTemplateFields]);

  const deleteTemplate = useCallback(async () => {
    if (!promptTemplateId) return;
    await deleteReq(`/api/prompt-templates/${encodeURIComponent(promptTemplateId)}`);
    setPromptTemplateId("");
    await loadPromptTemplates();
  }, [promptTemplateId, loadPromptTemplates]);

  return {
    promptTemplates,
    loadPromptTemplates,
    promptTemplateId,
    setPromptTemplateId,
    promptName,
    setPromptName,
    promptHookStyle,
    setPromptHookStyle,
    promptVisualStyle,
    setPromptVisualStyle,
    promptTone,
    setPromptTone,
    promptSystem,
    setPromptSystem,
    promptUser,
    setPromptUser,
    promptTopic,
    setPromptTopic,
    promptTargetAudience,
    setPromptTargetAudience,
    promptLangCode,
    setPromptLangCode,
    promptSlangLevel,
    setPromptSlangLevel,
    promptNarrTone,
    setPromptNarrTone,
    promptHookType,
    setPromptHookType,
    promptCtaType,
    setPromptCtaType,
    promptAspectRatio,
    setPromptAspectRatio,
    promptVisualStyle2,
    setPromptVisualStyle2,
    promptKeyPoints,
    setPromptKeyPoints,
    applyTemplateFromApi,
    applyTemplateFields,
    clearTemplate,
    saveTemplate,
    deleteTemplate,
  };
}

export type PromptLibraryStore = ReturnType<typeof usePromptLibrary>;
