import { useEffect, useRef, useState } from "react";
import { Btn, ExpandableTextArea, Input, Label } from "../../../components/ui";
import { postJson } from "../../../services/api";
import {
  PipelineSection as Section,
  type SectionStatus,
} from "../pipeline/PipelineSection";
import type { RunFn } from "../types";
import { FieldReviewHint, fieldReviewClass } from "./FieldReviewHint";
import { buildInferredNarrativeStructure } from "./promptIdentity";
import {
  isFieldHighlighted,
  isSectionIncomplete,
  type PromptValidationResult,
} from "./promptCompleteness";
import { InferredFieldShell } from "./InferredFieldShell";
import {
  fieldHighlightClass,
  inferredControlClass,
  labelHighlightClass,
} from "./promptFieldStyles";
import {
  buildPromptPreviewPayload,
  DEFAULT_PIPELINE_OUTPUT_STRUCTURE,
  SYSTEM_INSTRUCTIONS_PLACEHOLDER,
  USER_BASE_MODEL_LABEL,
  PROMPT_WRITER_OBJECTIVES_BLURB,
  USER_NARRATIVE_PLACEHOLDER,
} from "./promptInstructions";
import { isPendingReview, type PromptFieldKey } from "./promptPendingReview";
import { PromptValidationBanner } from "./PromptValidationBanner";
import { TranscriptsSessionBanner } from "../shared/TranscriptsSessionBanner";
import type { PromptLibraryStore } from "./usePromptLibrary";
import { promptTemplateStorageKey } from "./promptTemplateStorage";

function sectionStatusFromValidation(
  sectionDomId: string,
  highlight: PromptValidationResult | null | undefined,
): SectionStatus {
  const level = isSectionIncomplete(highlight, sectionDomId);
  if (level === "missing") return "incomplete";
  if (level === "warning") return "warning";
  return "default";
}

function LabelWithReview({
  label,
  pending,
  highlightLevel,
}: {
  label: string;
  pending: boolean;
  highlightLevel?: "missing" | "warning" | null;
}) {
  return (
    <div className="mb-1.5 flex flex-wrap items-center gap-2">
      <Label className={labelHighlightClass(highlightLevel ?? null)}>
        {label}
      </Label>
      {highlightLevel === "missing" ? (
        <span className="text-[10px] font-medium text-rose-600">Requerido</span>
      ) : null}
      <FieldReviewHint pending={pending} />
    </div>
  );
}

type PromptFieldVariant = "default" | "inferred" | "inferredNested";

function PromptField({
  id,
  highlight,
  pending,
  label,
  variant = "default",
  children,
}: {
  id: string;
  highlight: PromptValidationResult | null | undefined;
  pending?: boolean;
  label: string;
  variant?: PromptFieldVariant;
  children: React.ReactNode;
}) {
  const level = isFieldHighlighted(highlight, id);
  const body = (
    <>
      <LabelWithReview
        label={label}
        pending={!!pending}
        highlightLevel={level}
      />
      <div
        className={[fieldHighlightClass(level), fieldReviewClass(!!pending)]
          .filter(Boolean)
          .join(" ")}
      >
        {children}
      </div>
    </>
  );

  if (variant === "inferred") {
    return (
      <div id={`prompt-field-${id}`} className="scroll-mt-24">
        <InferredFieldShell highlightLevel={level} showSectionLabel>
          {body}
        </InferredFieldShell>
      </div>
    );
  }

  return (
    <div id={`prompt-field-${id}`} className="scroll-mt-24">
      {body}
    </div>
  );
}

function InferredParamsSection({
  lib,
  validationHighlight,
}: {
  lib: PromptLibraryStore;
  validationHighlight?: PromptValidationResult | null;
}) {
  const pending = lib.pendingReviewFields;
  const warnInferred =
    isFieldHighlighted(validationHighlight, "inferred_params") === "warning";
  const panelHighlight = warnInferred ? ("warning" as const) : null;
  const show =
    lib.promptTargetAudience.trim() ||
    lib.promptHookType.trim() ||
    lib.promptNarrTone.trim() ||
    lib.promptCtaType.trim() ||
    isPendingReview(pending, "target_audience") ||
    isPendingReview(pending, "hook_type") ||
    isPendingReview(pending, "narrative_tone") ||
    isPendingReview(pending, "cta_type") ||
    warnInferred;

  const fields: {
    id: string;
    key: PromptFieldKey;
    label: string;
    value: string;
    set: (v: string) => void;
  }[] = [
    {
      id: "hook_type",
      key: "hook_type",
      label: "Apertura (psicología)",
      value: lib.promptHookType,
      set: lib.setPromptHookType,
    },
    {
      id: "narrative_tone",
      key: "narrative_tone",
      label: "Tono (psicología)",
      value: lib.promptNarrTone,
      set: lib.setPromptNarrTone,
    },
    {
      id: "cta_type",
      key: "cta_type",
      label: "Cierre (psicología)",
      value: lib.promptCtaType,
      set: lib.setPromptCtaType,
    },
  ];

  return (
    <InferredFieldShell
      highlightLevel={panelHighlight}
      showSectionLabel
      className="md:col-span-2 scroll-mt-24 space-y-3"
    >
      <div id="prompt-field-inferred_params">
        {!show ? (
          <p className="text-[12px] text-slate-600">
            Analiza transcripts para inferir audiencia, hook, tono y CTA. Podrás revisar y
            ajustar cada valor antes de guardar.
          </p>
        ) : (
          <>
            <PromptField
              id="target_audience"
              highlight={validationHighlight}
              pending={isPendingReview(pending, "target_audience")}
              label="Target audience"
              variant="inferredNested"
            >
              <Input
                value={lib.promptTargetAudience}
                onChange={(e) => lib.setPromptTargetAudience(e.target.value)}
                className={[
                  inferredControlClass,
                  fieldReviewClass(isPendingReview(pending, "target_audience")),
                  fieldHighlightClass(
                    isFieldHighlighted(validationHighlight, "target_audience"),
                  ),
                ].join(" ")}
                placeholder="Se rellena al analizar transcripts — revisa y ajusta"
              />
            </PromptField>
            <div className="grid gap-3 sm:grid-cols-3">
              {fields.map((f) => (
                <PromptField
                  key={f.key}
                  id={f.id}
                  highlight={validationHighlight}
                  pending={isPendingReview(pending, f.key)}
                  label={f.label}
                  variant="inferredNested"
                >
                  <Input
                    value={f.value}
                    onChange={(e) => f.set(e.target.value)}
                    className={[
                      inferredControlClass,
                      fieldReviewClass(isPendingReview(pending, f.key)),
                      fieldHighlightClass(
                        isFieldHighlighted(validationHighlight, f.id),
                      ),
                    ].join(" ")}
                    placeholder="—"
                  />
                </PromptField>
              ))}
            </div>
          </>
        )}
      </div>
    </InferredFieldShell>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────
export function PromptLibraryPanel({
  run,
  locked,
  promptStepState,
  library,
  validationHighlight = null,
  sectionRevision = 0,
  onClearValidation,
  sessionLang = "en",
  sessionMinutes = 10,
  sessionKeywords = "",
  sessionContext = "",
  workApplied = "output/ui_session",
  topicSelected = true,
  onAfterRun,
}: {
  run: RunFn;
  locked: boolean;
  promptStepState: string;
  library: PromptLibraryStore;
  workApplied?: string;
  topicSelected?: boolean;
  provider?: string;
  model?: string;
  validationHighlight?: PromptValidationResult | null;
  sectionRevision?: number;
  onClearValidation?: () => void;
  onAfterRun?: () => void | Promise<void>;
  /** Valores de sesión para sustituir placeholders del modelo base (keywords → TEMA, context → ÁNGULO). */
  sessionLang?: string;
  sessionMinutes?: number;
  sessionKeywords?: string;
  sessionContext?: string;
}) {
  const lib = library;
  const libRef = useRef(lib);
  libRef.current = lib;
  const sessionAnalysisAppliedRef = useRef(false);
  const [hasSessionAnalysis, setHasSessionAnalysis] = useState(false);
  const [reapplying, setReapplying] = useState(false);
  const [manualEditMode, setManualEditMode] = useState(false);
  const [hasPromptArtifact, setHasPromptArtifact] = useState(false);
  const [promptConfirmedOnDisk, setPromptConfirmedOnDisk] = useState(false);

  useEffect(() => {
    setManualEditMode(false);
  }, [workApplied]);

  const promptIoLocked = promptStepState === "running";
  const effectiveLocked = locked && !manualEditMode;

  useEffect(() => {
    sessionAnalysisAppliedRef.current = false;
    let cancelled = false;
    void (async () => {
      try {
        let catalogTemplateId = "";
        const pr = await fetch(
          `/api/pipeline/prompt-artifact?work=${encodeURIComponent(workApplied)}`,
        );
        if (pr.ok && !cancelled) {
          const pj = (await pr.json()) as {
            exists?: boolean;
            confirmed?: boolean;
            artifact?: { catalog?: { prompt_template_id?: unknown } };
          };
          setHasPromptArtifact(!!pj.exists);
          setPromptConfirmedOnDisk(!!pj.confirmed);
          const cat = pj.artifact?.catalog;
          if (cat && typeof cat === "object" && cat.prompt_template_id != null) {
            catalogTemplateId = String(cat.prompt_template_id).trim();
          }
        }
        const storedId =
          sessionStorage.getItem(promptTemplateStorageKey(workApplied))?.trim() ||
          "";
        const templateId = catalogTemplateId || storedId;
        if (templateId && !cancelled) {
          libRef.current.setPromptTemplateId(templateId);
          await libRef.current.applyTemplateFromApi(templateId);
          sessionAnalysisAppliedRef.current = true;
        }

        const res = await fetch(
          `/api/session/transcripts?work=${encodeURIComponent(workApplied)}`,
        );
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as {
          has_prompt_analysis?: boolean;
          prompt_analysis?: Record<string, unknown>;
        };
        if (cancelled) return;
        setHasSessionAnalysis(!!data.has_prompt_analysis);

        if (sessionAnalysisAppliedRef.current) return;

        if (data.has_prompt_analysis && data.prompt_analysis) {
          sessionAnalysisAppliedRef.current = true;
          libRef.current.applyAnalysisResult(
            data.prompt_analysis as Parameters<typeof lib.applyAnalysisResult>[0],
          );
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workApplied, promptStepState]);

  const handleConfirmPrompt = () =>
    run("Confirmar prompt", async () => {
      await postJson("/api/pipeline/prompt/confirm", { work: workApplied });
      await onAfterRun?.();
      const pr = await fetch(
        `/api/pipeline/prompt-artifact?work=${encodeURIComponent(workApplied)}`,
      );
      if (pr.ok) {
        const pj = (await pr.json()) as { exists?: boolean; confirmed?: boolean };
        setHasPromptArtifact(!!pj.exists);
        setPromptConfirmedOnDisk(!!pj.confirmed);
      }
    });

  const promptUiLocked = locked || promptConfirmedOnDisk;
  const lockReason = promptIoLocked
    ? "Ejecutando paso Prompt…"
    : effectiveLocked
      ? "El paso Prompt ya se ejecutó: el catálogo y las secciones quedan fijados para no romper el guion en curso."
      : null;

  const previewSession = {
    languageCode: sessionLang,
    durationMinutes: sessionMinutes,
    tema: sessionKeywords,
    angulo: sessionContext,
    restricciones: lib.promptVideoRestrictions,
    fuentes: "",
  };
  const previewPayloadBase = {
    templateId: lib.promptTemplateId || null,
    name: lib.promptName,
    systemInstructions: lib.promptSystem,
    outputStructure: lib.promptOutputStructure,
    narrative: lib.promptUserNarrative,
    targetAudience: lib.promptTargetAudience,
    narrativeStructure: buildInferredNarrativeStructure({
      tone: lib.promptNarrTone,
      hook_type: lib.promptHookType,
      cta_type: lib.promptCtaType,
    }),
    session: previewSession,
  };

  const [previewFullscreen, setPreviewFullscreen] = useState(false);

  const previewJson = JSON.stringify(buildPromptPreviewPayload(previewPayloadBase), null, 2);
  const pending = lib.pendingReviewFields;
  const hasPendingReview = pending.size > 0;

  useEffect(() => {
    if (!previewFullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPreviewFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [previewFullscreen]);

  const sectionKey = (id: string) => `${id}-${sectionRevision}`;

  return (
    <div className={`space-y-4 ${effectiveLocked ? "opacity-90" : ""}`}>
      {promptIoLocked ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          <span className="font-semibold">Generando.</span> {lockReason} Espera a que termine
          antes de cambiar el template.
        </div>
      ) : null}
      {locked && !promptIoLocked ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          {effectiveLocked ? (
            <>
              <span className="font-semibold">Bloqueado.</span> {lockReason} Puedes desbloquear
              para cambiar de template o corregir campos; si regeneras el guion, usa{" "}
              <strong>Start step</strong> en Script Writer o <strong>Reset</strong> en la pipeline.
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Btn
                  type="button"
                  className="bg-white text-slate-900 hover:bg-slate-100"
                  onClick={() => setManualEditMode(true)}
                >
                  Editar prompt (desbloquear)
                </Btn>
              </div>
            </>
          ) : (
            <>
              <span className="font-semibold">Edición desbloqueada.</span> Puedes cambiar template,
              narrativa y restricciones. Los cambios no reescriben el guion hasta que ejecutes de
              nuevo Script Writer.
              <div className="mt-2">
                <Btn
                  type="button"
                  className="border border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
                  onClick={() => setManualEditMode(false)}
                >
                  Volver a bloquear
                </Btn>
              </div>
            </>
          )}
        </div>
      ) : null}

      {validationHighlight &&
      (validationHighlight.missing.length > 0 ||
        validationHighlight.warnings.length > 0) ? (
        <div className="space-y-2">
          <PromptValidationBanner result={validationHighlight} />
          {onClearValidation ? (
            <button
              type="button"
              className="text-[11px] text-slate-500 hover:text-slate-800"
              onClick={onClearValidation}
            >
              Ocultar aviso
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-sky-100 bg-sky-50/80 px-4 py-3 text-[12px] leading-relaxed text-sky-950">
        <p className="font-semibold text-sky-900">Prompt Writer · arquitectura narrativa</p>
        <p className="mt-1">{PROMPT_WRITER_OBJECTIVES_BLURB}</p>
        <p className="mt-1 text-sky-800/90">
          10 bloques creativos (estrella → mecanismo → psicología → tono → movimiento → visual → textura →
          rigor → naturalidad → prohibidos). Formato TTS/B-roll solo en el modelo base.
        </p>
      </div>

      {promptUiLocked && !promptIoLocked ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900">
          Prompt <strong>confirmado</strong>. El paso queda en <em>done</em> para continuar la pipeline.
        </div>
      ) : hasPromptArtifact && promptStepState !== "done" ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Hay <code className="text-[11px]">pipeline/prompt.json</code> pero el paso está en{" "}
          <strong>idle</strong>. Confírmalo para marcar <em>done</em> sin volver a ejecutar Start step.
        </div>
      ) : !hasPromptArtifact ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
          Aún no hay <code className="text-[11px]">prompt.json</code>. Usa Start step o confirma tras
          generar.
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Btn
          type="button"
          className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40"
          disabled={promptUiLocked || promptIoLocked || !hasPromptArtifact}
          onClick={() => void handleConfirmPrompt()}
        >
          Confirmar prompt (bloquear)
        </Btn>
      </div>

      <fieldset disabled={effectiveLocked || promptIoLocked} className="min-w-0 space-y-4 border-0 p-0">
        <div
          id="prompt-catalog"
          className={[
            "scroll-mt-20 overflow-hidden rounded-2xl border bg-white shadow-sm transition-shadow",
            isSectionIncomplete(validationHighlight, "prompt-catalog") ===
            "missing"
              ? "border-rose-300 ring-1 ring-rose-200"
              : "border-slate-200 shadow-slate-200/50",
          ].join(" ")}
        >
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3.5 sm:px-5">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-sky-500" aria-hidden />
              <h3 className="text-[15px] font-semibold tracking-tight text-slate-900">
                CATÁLOGO
              </h3>
            </div>
            <p className="mt-1 pl-4 text-[12px] leading-relaxed text-slate-500">
              Template guardado y nombre visible en el selector.
            </p>
          </div>
          <div className="flex flex-wrap items-end justify-between gap-3 px-4 py-4 sm:px-5">
            <div className="min-w-[160px] flex-1">
              <label className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Template
              </label>
              <select
                value={lib.promptTemplateId}
                onChange={async (e) => {
                  const id = e.target.value;
                  if (!id) {
                    lib.clearTemplate();
                    return;
                  }
                  lib.setPromptTemplateId(id);
                  await lib.applyTemplateFromApi(id);
                  sessionStorage.setItem(promptTemplateStorageKey(workApplied), id);
                }}
                className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-900 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
              >
                <option value="">(nuevo template)</option>
                {lib.promptTemplates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <InferredFieldShell className="min-w-[160px] flex-1 space-y-2">
              <PromptField
                id="name"
                highlight={validationHighlight}
                pending={isPendingReview(pending, "name")}
                label="Nombre"
                variant="inferredNested"
              >
                <Input
                  value={lib.promptName}
                  onChange={(e) => lib.setPromptName(e.target.value)}
                  className={[
                    inferredControlClass,
                    fieldReviewClass(isPendingReview(pending, "name")),
                    fieldHighlightClass(
                      isFieldHighlighted(validationHighlight, "name"),
                    ),
                  ].join(" ")}
                  placeholder="Se infiere al analizar transcripts — revisa y ajusta"
                />
              </PromptField>
            </InferredFieldShell>
            <div className="flex flex-wrap gap-2">
              <Btn
                className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                onClick={() =>
                  run("Recargar templates", async () => {
                    await lib.loadPromptTemplates();
                  })
                }
              >
                Reload
              </Btn>
              <Btn
                className="bg-slate-900 text-white hover:bg-slate-800"
                disabled={!lib.promptName.trim()}
                onClick={() =>
                  run("Guardar template", async () => {
                    const id = await lib.saveTemplate();
                    if (id && workApplied) {
                      sessionStorage.setItem(promptTemplateStorageKey(workApplied), id);
                      await lib.applyTemplateFromApi(id);
                    }
                  })
                }
              >
                Save
              </Btn>
              <Btn
                className="border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-40"
                disabled={!lib.promptTemplateId}
                onClick={() =>
                  run("Eliminar template", async () => {
                    if (!lib.promptTemplateId) return;
                    if (!confirm("¿Eliminar este template?")) return;
                    await lib.deleteTemplate();
                  })
                }
              >
                Delete
              </Btn>
            </div>
          </div>
        </div>

        {!effectiveLocked && !promptIoLocked ? (
          <div className="space-y-2">
            <TranscriptsSessionBanner workApplied={workApplied} />
            {!topicSelected ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                Elige un tema en <strong>Topic Generator</strong> con{" "}
                <strong>Usar este tema</strong> y pulsa{" "}
                <strong>Continuar al Prompt</strong>.
              </div>
            ) : null}
            {hasSessionAnalysis ? (
              <div className="flex flex-wrap items-center gap-2">
                <Btn
                  type="button"
                  className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
                  disabled={reapplying || effectiveLocked || promptIoLocked}
                  onClick={() =>
                    run("Aplicar análisis de sesión", async () => {
                      setReapplying(true);
                      try {
                        const data = await postJson<Record<string, unknown>>(
                          "/api/prompt-templates/generate-from-transcript",
                          {
                            work: workApplied,
                            transcript_text: "",
                            use_session: true,
                          },
                        );
                        lib.applyAnalysisResult(
                          data as Parameters<typeof lib.applyAnalysisResult>[0],
                        );
                      } finally {
                        setReapplying(false);
                      }
                    })
                  }
                >
                  {reapplying ? "Aplicando…" : "Reaplicar campos inferidos"}
                </Btn>
                <span className="text-[11px] text-slate-500">
                  Sobrescribe campos inferidos (incl. system instructions). No se aplica solo al
                  abrir si ya guardaste un template con Save.
                </span>
              </div>
            ) : null}
          </div>
        ) : null}

        {hasPendingReview ? (
          <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-900">
            Hay campos marcados como{" "}
            <strong>inferido — revisa antes de guardar</strong>. Corrígelos si
            hace falta y pulsa <strong>Save</strong> cuando estén listos.
          </div>
        ) : null}

        <div key={sectionKey("parametros-extra")}>
          <Section
            id="parametros-extra"
            title="PARÁMETROS EXTRA"
            accent="cyan"
            theme="light"
            status={sectionStatusFromValidation(
              "parametros-extra",
              validationHighlight,
            )}
            description="Audiencia, hook, tono y CTA inferidos de transcripts. Idioma, duración y tema van en el modelo base (placeholders)."
          >
            <div className="grid gap-4 md:grid-cols-2">
              <InferredParamsSection
                lib={lib}
                validationHighlight={validationHighlight}
              />
              <div className="md:col-span-2 rounded-xl border border-dashed border-slate-200 bg-slate-50/80 p-3">
                <Label>Restricciones del vídeo</Label>
                <span className="mb-2 block text-[11px] text-slate-500">
                  Solo esta sesión — sustituye {"{{RESTRICCIONES}}"} en el modelo base.
                </span>
                <ExpandableTextArea
                  value={lib.promptVideoRestrictions}
                  onChange={lib.setPromptVideoRestrictions}
                  placeholder="Ej: sin mencionar marcas, evitar política…"
                  modalTitle="Restricciones del vídeo"
                  variant="outputLight"
                />
              </div>
            </div>
          </Section>
        </div>

        <div key={sectionKey("system-instructions")}>
          <Section
            id="system-instructions"
            title="SYSTEM INSTRUCTIONS"
            accent="violet"
            theme="light"
            status={sectionStatusFromValidation(
              "system-instructions",
              validationHighlight,
            )}
            description="Destilado del estilo del canal (voz, ritmo, identidad). Inferido de transcripts; editable sin reanalizar."
          >
            <PromptField
              id="system_instructions"
              highlight={validationHighlight}
              pending={isPendingReview(pending, "system_instructions")}
              label="Estilo del canal"
              variant="inferred"
            >
              <ExpandableTextArea
                value={lib.promptSystem}
                onChange={lib.setPromptSystem}
                placeholder={SYSTEM_INSTRUCTIONS_PLACEHOLDER}
                modalTitle="SYSTEM INSTRUCTIONS"
                variant="inferred"
              />
            </PromptField>
          </Section>
        </div>

        <div key={sectionKey("user-instructions")}>
          <Section
            id="user-instructions"
            title="USER INSTRUCTIONS"
            accent="sky"
            theme="light"
            status={sectionStatusFromValidation(
              "user-instructions",
              validationHighlight,
            )}
            description="Modelo base (sesión, §11 técnico) + narrativa inferida (§§1–10: estrella creativa, mecanismo, psicología, tono, movimiento, mundo visual, textura humana, rigor, naturalidad, prohibidos)."
          >
            <div className="space-y-5">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <PromptField
                  id="output_structure"
                  highlight={validationHighlight}
                  label={USER_BASE_MODEL_LABEL}
                >
                  <span className="mb-2 block text-[11px] text-slate-500">
                    Usa {"{{LANGUAGE_CODE}}"}, {"{{DURACION_MINUTOS}}"}, {"{{TEMA}}"}, {"{{ANGULO}}"},
                    {"{{RESTRICCIONES}}"}, {"{{FUENTES}}"} — se rellenan al generar el guion. El idioma
                    sale de <strong>Analyse / Topic Generator</strong> (selector «Idioma de salida») y se
                    refleja el <strong>Idioma de salida</strong> del Topic Generator (
                    <strong>{sessionLang === "en" ? "en-US" : "es-ES"}</strong>).
                  </span>
                  <ExpandableTextArea
                    value={lib.promptOutputStructure}
                    onChange={lib.setPromptOutputStructure}
                    placeholder={DEFAULT_PIPELINE_OUTPUT_STRUCTURE.slice(0, 120) + "…"}
                    modalTitle={USER_BASE_MODEL_LABEL}
                    variant="outputLight"
                  />
                </PromptField>
              </div>
              <PromptField
                id="user_narrative"
                highlight={validationHighlight}
                pending={isPendingReview(
                  pending,
                  "user_instructions_narrative",
                )}
                label="Instrucciones narrativas"
                variant="inferred"
              >
                <ExpandableTextArea
                  value={lib.promptUserNarrative}
                  onChange={lib.setPromptUserNarrative}
                  placeholder={USER_NARRATIVE_PLACEHOLDER}
                  modalTitle="Instrucciones narrativas"
                  variant="inferred"
                />
              </PromptField>
            </div>
          </Section>
        </div>

      </fieldset>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
          <div>
            <div className="text-[15px] font-semibold tracking-tight text-slate-900">
              PREVIEW · Prompt Writer
            </div>
            <p className="text-[12px] leading-relaxed text-slate-500">
              JSON en tres bloques: <strong>catalog_saved</strong> (lo que guardas en UI/BD),{" "}
              <strong>composed_user_instructions</strong> (modelo base + narrativa con placeholders de sesión) y{" "}
              <strong>downstream_script_writer</strong> (transformación automática del backend al ejecutar Script
              Writer — no forma parte del catálogo Prompt).
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="button"
              tabIndex={0}
              className="cursor-pointer rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
              onClick={() => setPreviewFullscreen(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setPreviewFullscreen(true);
              }
            }}
          >
            Pantalla completa
          </div>
          </div>
        </div>
        <div
          role="button"
          tabIndex={0}
          aria-label="Ver preview a pantalla completa"
          onClick={() => setPreviewFullscreen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setPreviewFullscreen(true);
            }
          }}
          className={`min-h-[120px] w-full cursor-pointer bg-white px-4 py-3 text-left font-mono text-xs leading-relaxed outline-none transition hover:bg-slate-50 ${previewJson.trim() ? "text-slate-600" : "text-slate-400"}`}
        >
          <span className="block max-h-[200px] overflow-y-auto whitespace-pre-wrap">
            {previewJson.trim()
              ? previewJson.slice(0, 600) +
                (previewJson.length > 600 ? "\n…" : "")
              : "El preview aparecerá al rellenar los campos. Pulsa para ver el JSON completo."}
          </span>
        </div>
      </div>

      {previewFullscreen && (
        <div
          className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Preview Prompt Writer a pantalla completa"
        >
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">
                PREVIEW · Prompt Writer
              </span>
              <div className="flex flex-wrap gap-2">
                <Btn
                  type="button"
                  className="bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                  onClick={async () => {
                    await navigator.clipboard.writeText(previewJson);
                  }}
                >
                  Copiar
                </Btn>
                <Btn
                  type="button"
                  className="bg-slate-900 text-white hover:bg-slate-800"
                  onClick={() => setPreviewFullscreen(false)}
                >
                  Cerrar
                </Btn>
              </div>
            </div>
            <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap px-4 py-3 font-mono text-sm leading-relaxed text-slate-800">
              {previewJson}
            </pre>
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] leading-snug text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">
                Esc
              </kbd>{" "}
              cierra esta ventana.
              {previewJson.length > 0 && (
                <span> · {previewJson.length.toLocaleString()} caracteres</span>
              )}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
