import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { JsonEditor } from "../../../components/ui/JsonEditor";
import {
  postJson,
  putJson,
  readApiError,
  waitForPipelineStep,
} from "../../../services/api";
import type { RunFn } from "../types";
import { MetadataInputPreviewSection } from "./MetadataInputPreviewSection";
import { MetadataThumbnailsSection } from "./MetadataThumbnailsSection";
import {
  buildYoutubeDescriptionFromMetadata,
  parseMetadataForYoutube,
} from "./youtubeDescription";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";

type MetadataSettings = {
  target_platform: "youtube" | "tiktok" | "reels";
  target_keywords: string;
  target_keywords_effective?: string;
  target_keywords_source?: "manual" | "inferred" | null;
  system_prompt: string;
  default_system_prompt?: string;
};

type MetadataArtifact = {
  exists: boolean;
  metadata: Record<string, unknown> | null;
};

export function MetadataPanel({
  run,
  workApplied,
  lang,
  kw,
  ctx,
  minutes,
  provider,
  model,
  refreshPipeline,
  metadataStepState,
}: {
  run: RunFn;
  workApplied: string;
  lang: string;
  kw: string;
  ctx: string;
  minutes: number;
  provider: string;
  model: string;
  refreshPipeline: () => Promise<void>;
  metadataStepState: string;
}) {
  const [settings, setSettings] = useState<MetadataSettings | null>(null);
  const [artifact, setArtifact] = useState<MetadataArtifact | null>(null);
  const [editedArtifact, setEditedArtifact] = useState<string>("");
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const [previewReady, setPreviewReady] = useState(true);
  const [openaiModel, setOpenaiModel] = useState("gpt-4o-mini");
  const [copyYoutubeMsg, setCopyYoutubeMsg] = useState<string | null>(null);
  const [packagingExists, setPackagingExists] = useState(false);

  const generationRunning = metadataStepState === "running";

  useEffect(() => {
    void fetch("/api/llm/defaults")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { openai_model?: string } | null) => {
        if (d?.openai_model?.trim()) setOpenaiModel(d.openai_model.trim());
      })
      .catch(() => undefined);
  }, []);

  const langLabel = lang === "en" ? "English" : "Español";

  const loadSettings = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${lang}`,
      );
      if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
      const data = (await r.json()) as MetadataSettings;
      setSettings(data);
    } catch (e) {
      console.error("Failed to load metadata settings", e);
    }
  }, [workApplied, lang]);

  const loadArtifact = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/metadata?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
      const data = (await r.json()) as MetadataArtifact;
      setArtifact(data);
      setEditedArtifact(
        data.metadata ? JSON.stringify(data.metadata, null, 2) : "{}",
      );
    } catch (e) {
      console.error("Failed to load metadata artifact", e);
    }
  }, [workApplied]);

  const loadPackagingFlag = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/packaging?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) {
        setPackagingExists(false);
        return;
      }
      const data = (await r.json()) as { exists?: boolean };
      setPackagingExists(Boolean(data.exists));
    } catch {
      setPackagingExists(false);
    }
  }, [workApplied]);

  useEffect(() => {
    void loadSettings();
    void loadArtifact();
    void loadPackagingFlag();
  }, [loadSettings, loadArtifact, loadPackagingFlag]);

  useEffect(() => {
    if (metadataStepState === "done") {
      void loadArtifact();
    }
  }, [metadataStepState, loadArtifact]);

  const handleSaveSettings = () =>
    run("Guardar ajustes de metadatos", async () => {
      if (!settings) return;
      await putJson("/api/pipeline/metadata-settings", {
        work: workApplied,
        target_platform: settings.target_platform,
        target_keywords: settings.target_keywords,
        system_prompt: settings.system_prompt,
        target_keywords_source: settings.target_keywords.trim()
          ? "manual"
          : undefined,
        system_prompt_source: settings.system_prompt.trim()
          ? "manual"
          : undefined,
      });
      await loadSettings();
      await refreshPipeline();
    });

  const persistSettingsForGenerate = async () => {
    if (!settings) return;
    const r = await fetch(
      `/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${lang}`,
    );
    const onDisk = r.ok
      ? ((await r.json()) as MetadataSettings)
      : { target_keywords: "", system_prompt: "" };
    await putJson("/api/pipeline/metadata-settings", {
      work: workApplied,
      target_platform: settings.target_platform,
      target_keywords:
        mode === "manual" ? settings.target_keywords : "",
      system_prompt: mode === "manual" ? settings.system_prompt : "",
      target_keywords_source:
        mode === "manual" && settings.target_keywords.trim()
          ? "manual"
          : undefined,
      system_prompt_source:
        mode === "manual" && settings.system_prompt.trim()
          ? "manual"
          : undefined,
    });
  };

  const handleGenerate = () =>
    run("Generar metadatos (IA)", async () => {
      if (settings) {
        await persistSettingsForGenerate();
      }
      await postJson(`/api/pipeline/step/rerun`, {
        work: workApplied,
        step_id: "metadata",
        keywords: kw,
        context: ctx,
        lang,
        minutes,
        provider: "openai",
        model:
          provider === "openai" && model.trim() ? model.trim() : openaiModel,
      });
      await waitForPipelineStep(workApplied, "metadata");
      await refreshPipeline();
      await loadArtifact();
      setPreviewRefreshKey((k) => k + 1);
    });

  const handleCopyYoutubeDescription = async () => {
    const { metadata, parseError } = parseMetadataForYoutube(editedArtifact);
    if (parseError || !metadata) {
      setCopyYoutubeMsg(parseError ?? "JSON inválido");
      return;
    }
    const built = buildYoutubeDescriptionFromMetadata(metadata);
    if (!built.text.trim()) {
      setCopyYoutubeMsg(built.warnings[0] ?? "Nada que copiar");
      return;
    }
    try {
      await navigator.clipboard.writeText(built.text);
      const bits: string[] = [];
      if (built.hasDescription) bits.push("descripción");
      if (built.chapterCount > 0) {
        bits.push(
          `${built.chapterCount} capítulo${built.chapterCount === 1 ? "" : "s"}`,
        );
      }
      if (built.tagCount > 0) {
        bits.push(`${built.tagCount} tag${built.tagCount === 1 ? "" : "s"}`);
      }
      const hint = bits.length ? `Copiado (${bits.join(" · ")})` : "Copiado";
      setCopyYoutubeMsg(
        built.warnings.length ? `${hint} · ${built.warnings[0]}` : hint,
      );
    } catch {
      setCopyYoutubeMsg("No se pudo acceder al portapapeles");
    }
    window.setTimeout(() => setCopyYoutubeMsg(null), 4000);
  };

  const handleSaveArtifact = () =>
    run("Guardar metadatos (manual)", async () => {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(editedArtifact);
      } catch (e) {
        alert(`JSON inválido: ${e instanceof Error ? e.message : String(e)}`);
        return;
      }
      await putJson("/api/pipeline/metadata", {
        work: workApplied,
        metadata: parsed,
      });
      await refreshPipeline();
      await loadArtifact();
    });

  const handleLoadDefaultPrompt = () =>
    run("Cargar prompt por defecto", async () => {
      if (!settings) return;
      const r = await fetch(
        `/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${lang}&preview_platform=${settings.target_platform}`,
      );
      if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
      const data = (await r.json()) as MetadataSettings;
      if (data.default_system_prompt) {
        setSettings((s) =>
          s ? { ...s, system_prompt: data.default_system_prompt ?? "" } : null,
        );
      }
    });

  return (
    <div className="space-y-4">
      <PipelineStepConfirmBar
        stepId="metadata"
        stepLabel="Metadata"
        workApplied={workApplied}
        stepState={metadataStepState}
        run={run}
        onAfterRun={refreshPipeline}
      />
      <MetadataInputPreviewSection
        workApplied={workApplied}
        lang={lang}
        kw={kw}
        ctx={ctx}
        minutes={minutes}
        provider={provider}
        model={model}
        targetPlatform={settings?.target_platform ?? "youtube"}
        refreshKey={previewRefreshKey}
        onReadyChange={setPreviewReady}
      />

      <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        Con <strong>Packaging (Título + Miniatura)</strong> ya fijado, este paso solo deriva del
        guion la <strong>descripción</strong>, <strong>tags</strong> y <strong>capítulos</strong>{" "}
        (idioma: {langLabel}). Las ideas de miniatura salen de{" "}
        <code className="rounded bg-white px-1">packaging.json</code>, no se regeneran aquí.
        En automático, las instrucciones al modelo son compactas (plataforma + guion + sesión);
        no se reutiliza un system prompt largo guardado por error. La generación usa{" "}
        <strong>OpenAI API</strong> ({openaiModel}), no el proveedor Ollama del guion.
      </p>
      {settings?.system_prompt_source !== "manual" &&
      settings?.system_prompt?.trim() ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Hay un system prompt antiguo en disco; en modo automático se ignora. Borra el archivo o
          usa modo manual si quieres aplicarlo.
        </p>
      ) : null}
      {settings?.target_keywords_source === "inferred" &&
      settings.target_keywords?.trim() ? (
        <p className="rounded-lg border border-violet-100 bg-violet-50 px-3 py-2 text-xs text-violet-900">
          Última inferencia guardada (referencia):{" "}
          <span className="font-medium">{settings.target_keywords}</span> — no se
          reutiliza en modo automático; vuelve a generar para refrescar desde el guion.
        </p>
      ) : null}

      {/* Selector de modo */}
      <div className="flex gap-4 border-b border-slate-200 pb-2">
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="radio"
            name="metadata_mode"
            checked={mode === "auto"}
            onChange={() => setMode("auto")}
            className="text-violet-600 focus:ring-violet-500"
          />
          <span className="text-sm font-medium text-slate-700">
            IA Automática
          </span>
        </label>
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="radio"
            name="metadata_mode"
            checked={mode === "manual"}
            onChange={() => setMode("manual")}
            className="text-violet-600 focus:ring-violet-500"
          />
          <span className="text-sm font-medium text-slate-700">
            Configuración Manual
          </span>
        </label>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 p-4">
          <h3 className="text-sm font-semibold text-slate-800">
            {mode === "auto"
              ? "1. Generación Automática"
              : "1. Ajustes de Generación"}
          </h3>
          {mode === "manual" && (
            <Btn
              className="bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-100"
              onClick={handleSaveSettings}
              disabled={generationRunning || !settings}
            >
              Guardar Ajustes
            </Btn>
          )}
        </div>
        <div className="space-y-4 p-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Plataforma de Destino
            </span>
            <select
              className="max-w-xs rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
              value={settings?.target_platform ?? "youtube"}
              onChange={(e) =>
                setSettings(
                  (s) =>
                    ({
                      ...s,
                      target_platform: e.target.value,
                    }) as MetadataSettings,
                )
              }
              disabled={generationRunning}
            >
              <option value="youtube">YouTube</option>
              <option value="tiktok">TikTok</option>
              <option value="reels">Instagram Reels</option>
            </select>
            <p className="text-xs text-slate-500">
              Adapta los campos y el estilo de los metadatos a la plataforma. Se guarda al
              generar.
            </p>
          </label>

          {mode === "auto" && (
            <div className="pt-2">
              <Btn
                className="bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
                onClick={handleGenerate}
                disabled={generationRunning || !previewReady}
              >
                {generationRunning
                  ? "Generando..."
                  : "Generar Metadatos con IA"}
              </Btn>
              {!previewReady ? (
                <p className="mt-2 text-xs text-rose-600">
                  Revisa el checklist del preview (falta guion u otro requisito).
                </p>
              ) : null}
            </div>
          )}

          {mode === "manual" && (
            <label className="flex flex-col gap-1 border-t border-slate-100 pt-4">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Palabras Clave Objetivo (SEO)
              </span>
              <textarea
                className="min-h-[60px] w-full rounded-lg border border-slate-200 p-2 text-sm"
                placeholder="Ej: finanzas personales, invertir desde cero, errores de inversión"
                value={
                  settings?.target_keywords_source === "manual"
                    ? (settings?.target_keywords ?? "")
                    : ""
                }
                onChange={(e) =>
                  setSettings(
                    (s) =>
                      ({
                        ...s,
                        target_keywords: e.target.value,
                      }) as MetadataSettings,
                  )
                }
                disabled={generationRunning}
              />
              <p className="text-xs text-slate-500">
                Opcional: si las dejas vacías en automático, la IA las infiere del guion
                (platform.tags). El tema de sesión / Topic Generator no se usa como tags SEO.
              </p>
            </label>
          )}
        </div>
      </div>

      {mode === "manual" && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 p-4">
            <h3 className="text-sm font-semibold text-slate-800">
              2. System Prompt (Opcional)
            </h3>
            <Btn
              className="bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
              onClick={handleLoadDefaultPrompt}
              disabled={generationRunning || !settings}
            >
              Cargar prompt por defecto
            </Btn>
          </div>
          <div className="space-y-2 p-4">
            <textarea
              className="min-h-[200px] w-full rounded-lg border border-slate-200 p-2 font-mono text-xs"
              placeholder="Dejar vacío para usar el prompt por defecto del servidor..."
              value={
                settings?.system_prompt_source === "manual"
                  ? (settings?.system_prompt ?? "")
                  : ""
              }
              onChange={(e) =>
                setSettings(
                  (s) =>
                    ({
                      ...s,
                      system_prompt: e.target.value,
                    }) as MetadataSettings,
                )
              }
              disabled={generationRunning}
            />
            <p className="text-xs text-slate-500">
              Opcional y avanzado: añade reglas extra. En automático se usan
              instrucciones compactas (plataforma + idioma de sesión + guion).
              Guárdalo con &quot;Guardar Ajustes&quot; para activarlo.
            </p>
          </div>
        </div>
      )}

      <MetadataThumbnailsSection
        run={run}
        workApplied={workApplied}
        generationRunning={generationRunning}
        artifactExists={Boolean(artifact?.exists) || packagingExists}
        refreshPipeline={refreshPipeline}
      />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 p-4">
          <h3 className="text-sm font-semibold text-slate-800">
            {mode === "auto"
              ? "2. Artefacto Generado (metadata.json)"
              : "3. Artefacto Generado (metadata.json)"}
          </h3>
          <div className="flex flex-wrap items-center gap-2">
            <Btn
              type="button"
              className="bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40"
              onClick={() => void handleCopyYoutubeDescription()}
              disabled={generationRunning || !artifact?.exists}
              title="platform.description + capítulos + hashtags desde platform.tags"
            >
              Copiar descripción YouTube
            </Btn>
            <Btn
              className="bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 hover:bg-emerald-100"
              onClick={handleSaveArtifact}
              disabled={generationRunning || !artifact?.exists}
            >
              Guardar Cambios en JSON
            </Btn>
          </div>
        </div>
        <div className="p-4">
          {copyYoutubeMsg ? (
            <p
              className={`mb-3 text-xs leading-snug ${
                copyYoutubeMsg.startsWith("Copiado")
                  ? "text-emerald-700"
                  : "text-amber-800"
              }`}
            >
              {copyYoutubeMsg}
            </p>
          ) : null}
          {artifact?.exists ? (
            <JsonEditor
              value={editedArtifact}
              onChange={setEditedArtifact}
              readOnly={generationRunning}
              height="600px"
            />
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
              <p>No se ha generado ningún artefacto de metadatos todavía.</p>
              <p className="mt-1">Ejecuta la generación para crearlo.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
