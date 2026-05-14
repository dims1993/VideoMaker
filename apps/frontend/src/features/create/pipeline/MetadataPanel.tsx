import { useCallback, useEffect, useState } from "react";
import { Btn, ExpandableTextArea, Label, Select } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

type PlatformId = "youtube" | "tiktok" | "reels";

export function MetadataPanel({
  run,
  workApplied,
  lang,
  refreshPipeline,
  metadataStepState,
}: {
  run: RunFn;
  workApplied: string;
  lang: string;
  refreshPipeline: () => Promise<void>;
  metadataStepState: string;
}) {
  const [jsonText, setJsonText] = useState("");
  const [loaded, setLoaded] = useState(false);
  const generationRunning = metadataStepState === "running";

  const [targetPlatform, setTargetPlatform] = useState<PlatformId>("youtube");
  const [targetKeywords, setTargetKeywords] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [settingsHydrated, setSettingsHydrated] = useState(false);

  const [imagePromptsText, setImagePromptsText] = useState("");
  const [imagePromptsLoaded, setImagePromptsLoaded] = useState(false);

  const [includeAvatar, setIncludeAvatar] = useState(false);
  const [avatarName, setAvatarName] = useState<string | null>(null);

  const loadMetadata = useCallback(async () => {
    const r = await fetch(`/api/pipeline/metadata?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; metadata?: Record<string, unknown> | null };
    if (j.exists && j.metadata && typeof j.metadata === "object") {
      setJsonText(JSON.stringify(j.metadata, null, 2)); setLoaded(true);
    } else { setJsonText(""); setLoaded(false); }
  }, [workApplied]);

  const hydrateSettings = useCallback(async () => {
    setSettingsHydrated(false);
    const r = await fetch(`/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${encodeURIComponent(lang)}`);
    if (!r.ok) {
      setSettingsHydrated(true);
      return;
    }
    const j = (await r.json()) as { target_platform?: string; target_keywords?: string; system_prompt?: string };
    if (j.target_platform === "youtube" || j.target_platform === "tiktok" || j.target_platform === "reels") setTargetPlatform(j.target_platform);
    if (j.target_keywords !== undefined) setTargetKeywords(j.target_keywords);
    if (j.system_prompt !== undefined) setSystemPrompt(j.system_prompt);
    setSettingsHydrated(true);
  }, [workApplied, lang]);

  const persistSettings = useCallback(async () => {
    await putJson(`/api/pipeline/metadata-settings`, {
      work: workApplied,
      target_platform: targetPlatform,
      target_keywords: targetKeywords,
      system_prompt: systemPrompt.trim(),
    });
  }, [workApplied, targetPlatform, targetKeywords, systemPrompt]);

  const loadAvatarInfo = useCallback(async () => {
    const r = await fetch(`/api/pipeline/image-prompt-writer-settings?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { use_avatar?: boolean; avatar_id?: string; avatar_description?: string };
    if (!j.use_avatar || !j.avatar_id) { setAvatarName(null); return; }
    const ra = await fetch(`/api/avatars/${encodeURIComponent(j.avatar_id)}`);
    if (!ra.ok) { setAvatarName(null); return; }
    const av = (await ra.json()) as { name?: string };
    setAvatarName(av.name ?? null);
  }, [workApplied]);

  const loadImagePrompts = useCallback(async () => {
    const r = await fetch(`/api/pipeline/image-prompts?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) { setImagePromptsText(""); setImagePromptsLoaded(false); return; }
    const j = (await r.json()) as { exists?: boolean; bundle?: unknown };
    if (j.exists && j.bundle) {
      setImagePromptsText(JSON.stringify(j.bundle, null, 2));
      setImagePromptsLoaded(true);
    } else {
      setImagePromptsText(""); setImagePromptsLoaded(false);
    }
  }, [workApplied]);

  useEffect(() => { void loadMetadata(); }, [loadMetadata, metadataStepState, workApplied]);
  useEffect(() => { void hydrateSettings(); }, [hydrateSettings]);
  useEffect(() => { void loadImagePrompts(); }, [loadImagePrompts]);
  useEffect(() => { void loadAvatarInfo(); }, [loadAvatarInfo]);

  useEffect(() => {
    if (!settingsHydrated) return;
    const id = window.setTimeout(() => {
      void persistSettings().catch((e) => console.error("metadata-settings persist", e));
    }, 650);
    return () => window.clearTimeout(id);
  }, [settingsHydrated, targetPlatform, targetKeywords, systemPrompt, persistSettings]);

  const onPlatformChange = (p: PlatformId) => {
    setTargetPlatform(p);
    void (async () => {
      const r = await fetch(
        `/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${encodeURIComponent(lang)}&preview_platform=${encodeURIComponent(p)}`,
      );
      if (!r.ok) return;
      const j = (await r.json()) as { default_system_prompt?: string };
      if (typeof j.default_system_prompt === "string") setSystemPrompt(j.default_system_prompt);
    })();
  };

  const handleSave = async () => {
    const trimmed = jsonText.trim();
    if (!trimmed) throw new Error("El cuadro está vacío. Usa «Start step» para generar o pega un objeto JSON antes de guardar.");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(trimmed) as Record<string, unknown>;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("El JSON debe ser un objeto en la raíz { … }, no un array.");
    } catch (e) {
      throw new Error(e instanceof SyntaxError ? "JSON inválido (revisa comillas, comas y llaves)." : e instanceof Error ? e.message : String(e));
    }
    await putJson(`/api/pipeline/metadata`, { work: workApplied, metadata: parsed });
    await loadMetadata();
    await refreshPipeline();
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">

      {/* Info — orden del proceso */}
      <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
        <span className="font-semibold">Metadata — orden del proceso.</span>{" "}
        <span className="text-amber-200/95">
          <strong className="text-amber-100">1</strong> Ajustes (plataforma, claves, system prompt) antes del LLM.{" "}
          <strong className="text-amber-100">2</strong> En la tarjeta del paso, «Start step» genera el JSON; aquí revisas o editas <code className="rounded bg-amber-900/40 px-1">pipeline/metadata.json</code> y guardas en sesión.{" "}
          <strong className="text-amber-100">3</strong> Si en <code className="rounded bg-amber-900/40 px-1">editorial.thumbnail_ideas</code> hay ideas, envíalas al pipeline de imágenes.
        </span>{" "}
        Incluye título, descripción por actos, capítulos,{" "}
        <code className="rounded bg-amber-900/40 px-1">hook_type</code>/<code className="rounded bg-amber-900/40 px-1">hook_summary</code>, production/marketing y <code className="rounded bg-amber-900/40 px-1">_gen</code>.
      </div>

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Generando metadata con el modelo… el editor va en solo lectura hasta que termine.
        </div>
      )}

      {/* 1 · Ajustes (entrada al LLM) */}
      <Section id="meta-settings" badge="1" title="Ajustes de generación" description="Antes de «Start step» en la tarjeta del paso. Los cambios se guardan solos en la sesión. Al cambiar la plataforma se inserta el prompt predeterminado del servidor (editable en pantalla completa).">
        <div className="space-y-4">
          <div>
            <Label>Plataforma destino</Label>
            <Select value={targetPlatform} onChange={(e) => onPlatformChange(e.target.value as PlatformId)} disabled={generationRunning || !settingsHydrated}>
              <option value="youtube">YouTube</option>
              <option value="tiktok">TikTok</option>
              <option value="reels">Reels (Instagram)</option>
            </Select>
            <p className="mt-1 text-[11px] leading-snug text-slate-500">
              Al elegir una plataforma se carga el prompt predeterminado del servidor para esa red (puedes editarlo abajo).
            </p>
          </div>

          <div>
            <ExpandableTextArea
              label="Palabras clave objetivo"
              value={targetKeywords}
              onChange={setTargetKeywords}
              placeholder='"comprar casa", fondos indexados, temas SEO…'
              modalTitle="Metadata · Palabras clave objetivo"
              variant="output"
              disabled={generationRunning || !settingsHydrated}
              disabledTitle={generationRunning ? "No disponible mientras se genera" : !settingsHydrated ? "Cargando ajustes desde la sesión…" : undefined}
            />
          </div>

          <div>
            <ExpandableTextArea
              label="System prompt"
              value={systemPrompt}
              onChange={setSystemPrompt}
              placeholder="Vacío en disco = en generación se usa el predeterminado del servidor para la plataforma."
              modalTitle="Metadata · System prompt"
              variant="output"
              disabled={generationRunning || !settingsHydrated}
              disabledTitle={generationRunning ? "No disponible mientras se genera" : !settingsHydrated ? "Cargando ajustes desde la sesión…" : undefined}
            />
            <p className="mb-0 mt-1 text-[11px] leading-snug text-slate-500">
              Clic en el recuadro o «✎ editar» · <kbd className="rounded bg-slate-700 px-1 font-mono text-[10px]">Guardar</kbd> en el modal aplica el texto y se guarda en la sesión unos instantes después.
            </p>
          </div>
        </div>
      </Section>

      {/* 2 · Salida JSON (tras Start step o edición manual) */}
      <Section id="meta-output" badge="2" title="Salida · metadata.json" description="Resultado del LLM o edición manual. Guarda en sesión para escribir disco antes del paso 3.">
        <div className="space-y-2">
          <div className="flex flex-wrap justify-end gap-2">
            <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadMetadata()}>Recargar desde disco</Btn>
          </div>
          <ExpandableTextArea
            value={jsonText}
            onChange={setJsonText}
            placeholder="Tras «Start step» aparecerá JSON (version, platform, editorial, production…)"
            modalTitle="pipeline/metadata.json"
            variant="output"
            disabled={generationRunning}
            disabledTitle={generationRunning ? "No disponible mientras se genera" : undefined}
          />
          <div className="flex flex-wrap gap-2">
            <Btn className="bg-white text-slate-900 hover:bg-slate-100" disabled={generationRunning}
              onClick={() => run("Guardar metadata", handleSave)}>
              Guardar en sesión
            </Btn>
            <span className="self-center text-[11px] text-slate-500">
              Tras editar en pantalla completa, confirma aquí para escribir <code className="rounded bg-slate-700 px-1">pipeline/metadata.json</code>.
            </span>
          </div>
        </div>
      </Section>

      {/* 3 · Miniaturas (lee metadata.json ya guardado) */}
      <Section id="meta-thumbnails-push" badge="3" title="Miniaturas → pipeline de imágenes" description="Solo después de tener metadata en disco con editorial.thumbnail_ideas. Copia esas cadenas a pipeline/image_prompts.json para el paso Imágenes.">
        <div className="space-y-3">
          {/* Toggle avatar */}
          <div className="flex flex-wrap items-start gap-3 rounded-xl border border-slate-700 bg-slate-800/50 px-3 py-2.5">
            <label className="flex cursor-pointer items-center gap-2.5">
              <div
                role="checkbox"
                aria-checked={includeAvatar}
                tabIndex={0}
                className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${includeAvatar ? "bg-blue-500" : "bg-slate-600"}`}
                onClick={() => setIncludeAvatar((v) => !v)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setIncludeAvatar((v) => !v); } }}
              >
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${includeAvatar ? "translate-x-4" : "translate-x-0.5"}`} />
              </div>
              <span className="text-xs font-medium text-slate-200">Incluir avatar en las miniaturas</span>
            </label>
            {includeAvatar && (
              <span className="text-[11px] text-slate-400">
                {avatarName
                  ? <>Avatar: <span className="font-medium text-blue-300">{avatarName}</span> (configurado en Image Prompt Writer)</>
                  : <span className="text-amber-400">No hay avatar configurado en Image Prompt Writer — se usará la descripción por defecto.</span>
                }
              </span>
            )}
            {!includeAvatar && (
              <span className="text-[11px] text-slate-500">
                Activa para añadir el personaje del canal a cada prompt de miniatura.
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
              disabled={generationRunning || !loaded}
              title={!loaded ? "Genera y guarda metadata antes (paso 2) para tener editorial.thumbnail_ideas" : undefined}
              onClick={() => run("Miniaturas → pipeline imágenes", async () => {
                await postJson(`/api/pipeline/metadata/push-thumbnails-to-images`, { work: workApplied, include_avatar: includeAvatar });
                await refreshPipeline();
                await loadImagePrompts();
              })}>
              Generar miniaturas → pipeline de imágenes
            </Btn>
            <span className="text-[11px] text-slate-400">
              Origen: <code className="rounded bg-slate-700 px-1">editorial.thumbnail_ideas</code> en el JSON del paso 2.
            </span>
          </div>

          {imagePromptsLoaded && (
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-medium text-slate-400">pipeline/image_prompts.json generado</span>
                <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700 text-[11px] py-0.5 px-2" onClick={() => void loadImagePrompts()}>
                  Recargar
                </Btn>
              </div>
              <ExpandableTextArea
                value={imagePromptsText}
                onChange={setImagePromptsText}
                placeholder=""
                modalTitle="pipeline/image_prompts.json"
                variant="output"
              />
            </div>
          )}

          {!imagePromptsLoaded && (
            <p className="text-[11px] text-slate-500">
              Aún no hay <code className="rounded bg-slate-800 px-1">image_prompts.json</code> en disco. Pulsa el botón de arriba para generarlo.
            </p>
          )}
        </div>
      </Section>

      {!loaded && !generationRunning && (
        <p className="text-xs text-slate-500">
          Sin <code className="rounded bg-slate-800 px-1">metadata.json</code> en disco: completa el paso <strong className="text-slate-300">1</strong>, ejecuta <strong className="text-slate-300">Start step</strong> en la tarjeta del paso Metadata y revisa el paso <strong className="text-slate-300">2</strong>.
        </p>
      )}
    </div>
  );
}
