import { useCallback, useState } from "react";
import { deleteReq, postJson, putJson } from "../../../services/api";
import { buildInferredNarrativeStructure, mergeLegacyIdentityIntoSystem } from "./promptIdentity";
import {
  DEFAULT_PIPELINE_OUTPUT_STRUCTURE,
  splitUserInstructions,
} from "./promptInstructions";
import type { PromptFieldKey } from "./promptPendingReview";

export type PromptTemplateListItem = { id: string; name: string };

type TemplatePayload = {
  name?: string;
  hook_style?: string;
  visual_style?: string;
  tone?: string;
  system_instructions?: string;
  user_instructions?: string;
  user_instructions_narrative?: string;
  params_json?: Record<string, unknown>;
};

function collectPendingFromAnalysis(t: TemplatePayload): Set<PromptFieldKey> {
  const pending = new Set<PromptFieldKey>();
  if ((t.name || "").trim()) pending.add("name");
  if ((t.system_instructions || "").trim()) pending.add("system_instructions");
  const narr =
    (t.user_instructions_narrative || "").trim() ||
    (t.user_instructions || "").trim();
  if (narr) pending.add("user_instructions_narrative");
  const pj = (t.params_json || {}) as {
    target_audience?: string;
    language_context?: { code?: string };
    narrative_structure?: { tone?: string; hook_type?: string; cta_type?: string };
    target_duration_minutes?: number;
  };
  if ((pj.target_audience || "").trim()) pending.add("target_audience");
  const ns = pj.narrative_structure;
  if ((ns?.tone || "").trim()) pending.add("narrative_tone");
  if ((ns?.hook_type || "").trim()) pending.add("hook_type");
  if ((ns?.cta_type || "").trim()) pending.add("cta_type");
  return pending;
}

export function usePromptLibrary() {
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplateListItem[]>([]);

  const [promptTemplateId, setPromptTemplateId] = useState("");
  const [promptName, setPromptName] = useState("");
  const [promptSystem, setPromptSystem] = useState("");
  const [promptOutputStructure, setPromptOutputStructure] = useState(DEFAULT_PIPELINE_OUTPUT_STRUCTURE);
  const [promptUserNarrative, setPromptUserNarrative] = useState("");
  const [promptTopic, setPromptTopic] = useState("");
  const [promptTargetAudience, setPromptTargetAudience] = useState("");
  const [promptLangCode, setPromptLangCode] = useState("es-ES");
  const [promptNarrTone, setPromptNarrTone] = useState("");
  const [promptHookType, setPromptHookType] = useState("");
  const [promptCtaType, setPromptCtaType] = useState("");
  const [promptTargetDurationMinutes, setPromptTargetDurationMinutes] = useState(10);
  const [promptVideoRestrictions, setPromptVideoRestrictions] = useState("");
  const [pendingReviewFields, setPendingReviewFields] = useState<Set<PromptFieldKey>>(new Set());

  const clearPendingReview = useCallback((key: PromptFieldKey) => {
    setPendingReviewFields((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }, []);

  const clearAllPendingReview = useCallback(() => {
    setPendingReviewFields(new Set());
  }, []);

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
      hook_style: "",
      visual_style: "",
      tone: "",
      system_instructions: promptSystem,
      user_instructions: promptUserNarrative,
      params_json: {
        target_audience: promptTargetAudience,
        narrative_structure: buildInferredNarrativeStructure({
          tone: promptNarrTone,
          hook_type: promptHookType,
          cta_type: promptCtaType,
        }),
        output_structure:
          promptOutputStructure.trim() ||
          (promptUserNarrative.trim() ? DEFAULT_PIPELINE_OUTPUT_STRUCTURE : ""),
      },
    };
  }, [
    promptName,
    promptSystem,
    promptUserNarrative,
    promptOutputStructure,
    promptTargetAudience,
    promptNarrTone,
    promptHookType,
    promptCtaType,
  ]);

  const applyTemplateFields = useCallback((t: TemplatePayload) => {
    setPromptName(t.name || "");
    setPromptSystem(
      mergeLegacyIdentityIntoSystem(t.system_instructions || "", {
        hook_style: t.hook_style,
        visual_style: t.visual_style,
        tone: t.tone,
      }),
    );
    const pj = (t.params_json || {}) as {
      target_audience?: string;
      language_context?: { code?: string };
      narrative_structure?: { tone?: string; hook_type?: string; cta_type?: string };
      target_duration_minutes?: number;
      output_structure?: string;
      channel_expressions?: string;
    };
    const storedOut = (pj.output_structure || "").trim();
    const narrRaw =
      (t.user_instructions_narrative || "").trim() ||
      (t.user_instructions || "").trim();
    if (storedOut) {
      setPromptOutputStructure(storedOut);
      setPromptUserNarrative(narrRaw);
    } else {
      const split = splitUserInstructions(narrRaw);
      setPromptOutputStructure(split.outputStructure);
      setPromptUserNarrative(split.narrative);
    }
    setPromptTargetAudience(pj.target_audience || "");
    setPromptNarrTone(pj.narrative_structure?.tone || "");
    setPromptHookType(pj.narrative_structure?.hook_type || "");
    setPromptCtaType(pj.narrative_structure?.cta_type || "");
  }, []);

  const applyAnalysisResult = useCallback(
    (t: TemplatePayload) => {
      const narrative =
        (t.user_instructions_narrative || "").trim() ||
        (t.user_instructions || "").trim();
      applyTemplateFields({
        ...t,
        user_instructions: narrative,
        user_instructions_narrative: narrative,
      });
      setPendingReviewFields(collectPendingFromAnalysis(t));
    },
    [applyTemplateFields],
  );

  const saveTemplate = useCallback(async (): Promise<string> => {
    const base = buildPayload();
    const nameForApi =
      (base.name || "").trim() || "Plantilla sin nombre";
    const payload = { ...base, name: nameForApi };
    if (promptTemplateId) {
      await putJson(`/api/prompt-templates/${encodeURIComponent(promptTemplateId)}`, payload);
      await loadPromptTemplates();
      clearAllPendingReview();
      return promptTemplateId;
    } else {
      const res = await postJson<{ ok?: boolean; template?: { id?: string | number } }>(`/api/prompt-templates`, payload);
      const rawId = res?.template?.id;
      const id = rawId != null && rawId !== "" ? String(rawId) : "";
      if (id) {
        setPromptTemplateId(id);
        if (!(promptName || "").trim()) {
          setPromptName(nameForApi);
        }
      }
      await loadPromptTemplates();
      clearAllPendingReview();
      return id;
    }
  }, [buildPayload, promptTemplateId, loadPromptTemplates, promptName, clearAllPendingReview]);

  const clearTemplate = useCallback(() => {
    setPromptTemplateId("");
    setPromptName("");
    setPromptSystem("");
    setPromptOutputStructure(DEFAULT_PIPELINE_OUTPUT_STRUCTURE);
    setPromptUserNarrative("");
    setPromptTopic("");
    setPromptTargetAudience("");
    setPromptLangCode("es-ES");
    setPromptNarrTone("");
    setPromptHookType("");
    setPromptCtaType("");
    setPromptTargetDurationMinutes(10);
    setPromptVideoRestrictions("");
    clearAllPendingReview();
  }, [clearAllPendingReview]);

  const applyTemplateFromApi = useCallback(
    async (id: string) => {
      if (!id) return;
      const r = await fetch(`/api/prompt-templates/${encodeURIComponent(id)}`);
      if (!r.ok) return;
      const t = (await r.json()) as TemplatePayload;
      applyTemplateFields(t);
      clearAllPendingReview();
    },
    [applyTemplateFields, clearAllPendingReview],
  );

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
    setPromptName: (v: string) => {
      setPromptName(v);
      clearPendingReview("name");
    },
    promptSystem,
    setPromptSystem: (v: string) => {
      setPromptSystem(v);
      clearPendingReview("system_instructions");
    },
    promptOutputStructure,
    setPromptOutputStructure: (v: string) => {
      setPromptOutputStructure(v);
      clearPendingReview("user_output_structure");
    },
    promptUserNarrative,
    setPromptUserNarrative: (v: string) => {
      setPromptUserNarrative(v);
      clearPendingReview("user_instructions_narrative");
    },
    promptTopic,
    setPromptTopic,
    promptTargetAudience,
    setPromptTargetAudience: (v: string) => {
      setPromptTargetAudience(v);
      clearPendingReview("target_audience");
    },
    promptLangCode,
    setPromptLangCode: (v: string) => {
      setPromptLangCode(v);
      clearPendingReview("language_code");
    },
    promptNarrTone,
    setPromptNarrTone: (v: string) => {
      setPromptNarrTone(v);
      clearPendingReview("narrative_tone");
    },
    promptHookType,
    setPromptHookType: (v: string) => {
      setPromptHookType(v);
      clearPendingReview("hook_type");
    },
    promptCtaType,
    setPromptCtaType: (v: string) => {
      setPromptCtaType(v);
      clearPendingReview("cta_type");
    },
    promptTargetDurationMinutes,
    setPromptTargetDurationMinutes: (v: number) => {
      setPromptTargetDurationMinutes(v);
      clearPendingReview("target_duration_minutes");
    },
    promptVideoRestrictions,
    setPromptVideoRestrictions,
    pendingReviewFields,
    clearPendingReview,
    applyTemplateFromApi,
    applyTemplateFields,
    applyAnalysisResult,
    clearTemplate,
    saveTemplate,
    deleteTemplate,
  };
}

export type PromptLibraryStore = ReturnType<typeof usePromptLibrary>;
