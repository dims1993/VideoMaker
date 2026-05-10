import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Btn, Input, Label, Select, TextArea } from "../../../components/ui";
import { patchJson, postJson, putJson } from "../../../services/api";
import type {
  ScriptWriterLibraryStore,
  ScriptWriterNarrativePreset,
} from "../scriptWriter/useScriptWriterLibrary";
import type { RunFn } from "../types";

type NarrativePresetApi = {
  id: string;
  name: string;
  weights: number[];
  descriptions: string[];
};

/** Si Ollama no responde, mostrar lista razonable hasta que el usuario recargue. */
const FALLBACK_OLLAMA_MODELS = [
  "qwen2.5:14b",
  "qwen2.5-coder:7b",
  "deepseek-coder-v2:16b",
  "llama3.2:latest",
];

type LlmDefaultsResponse = {
  llm_provider: string;
  ollama_model: string;
  openai_model: string;
};

export function ScriptWriterPanel({
  run,
  workApplied,
  locked,
  scriptStepState,
  library,
  kw,
  setKw,
  ctx,
  setCtx,
  lang,
  setLang,
  minutes,
  setMinutes,
  provider,
  setProvider,
  model,
  setModel,
  scriptFragmentIndex,
  setScriptFragmentIndex,
  refreshPipeline,
}: {
  run: RunFn;
  workApplied: string;
  locked: boolean;
  scriptStepState: string;
  library: ScriptWriterLibraryStore;
  kw: string;
  setKw: (v: string) => void;
  ctx: string;
  setCtx: (v: string) => void;
  lang: string;
  setLang: (v: string) => void;
  minutes: number;
  setMinutes: (v: number) => void;
  provider: string;
  setProvider: (v: string) => void;
  model: string;
  setModel: (v: string) => void;
  scriptFragmentIndex: number | null;
  setScriptFragmentIndex: (v: number | null) => void;
  refreshPipeline: () => Promise<void>;
}) {
  const lib = library;
  const [scriptText, setScriptText] = useState("");
  const [ollamaNames, setOllamaNames] = useState<string[]>([]);
  const [ollamaListHint, setOllamaListHint] = useState<string | null>(null);
  const [llmDefaults, setLlmDefaults] = useState<LlmDefaultsResponse | null>(
    null,
  );
  const defaultsAppliedRef = useRef(false);
  const [fragExists, setFragExists] = useState(false);
  const [fragSteps, setFragSteps] = useState<
    { id: string; label: string; status: string }[]
  >([]);
  const [narrativePresets, setNarrativePresets] = useState<
    NarrativePresetApi[]
  >([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/narrative-presets");
        if (!r.ok || cancelled) return;
        const j = (await r.json()) as { presets?: NarrativePresetApi[] };
        if (!cancelled && Array.isArray(j.presets))
          setNarrativePresets(j.presets);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Si el template trae `narrative_preset` pero sin `fragment_minute_weights`, rellenamos la caja para que coincida con la categoría. */
  useEffect(() => {
    if (lib.swStructure !== "four_act") return;
    const id = lib.swNarrativePreset;
    if (!id || id === "custom") return;
    if (lib.swFragmentWeights.trim()) return;
    const p = narrativePresets.find((x) => x.id === id);
    if (p?.weights?.length === 4)
      lib.setSwFragmentWeights(p.weights.join(", "));
  }, [
    narrativePresets,
    lib.swStructure,
    lib.swNarrativePreset,
    lib.swFragmentWeights,
    lib.setSwFragmentWeights,
  ]);

  const fourActPreview = useMemo(() => {
    if (lib.swStructure !== "four_act") return null;
    const totalMin = Number.isFinite(minutes) && minutes > 0 ? minutes : 20;
    let w: number[] | null = null;
    let descriptions: string[] = [];
    const presetId = lib.swNarrativePreset;
    if (presetId && presetId !== "custom") {
      const p = narrativePresets.find((x) => x.id === presetId);
      if (p?.weights?.length === 4) {
        w = p.weights;
        descriptions = p.descriptions;
      }
    }
    if (!w && lib.swFragmentWeights.trim()) {
      const parts = lib.swFragmentWeights
        .split(/[,;\n]+/)
        .map((x) => x.trim())
        .filter(Boolean)
        .map(Number);
      if (parts.length === 4 && parts.every((x) => !Number.isNaN(x))) {
        const sum = parts.reduce((a, b) => a + b, 0);
        if (sum > 0) {
          w = parts.map((x) => x / sum);
          descriptions = ["Bloque 1", "Bloque 2", "Bloque 3", "Bloque 4"];
        }
      }
    }
    if (!w) {
      w = [0.15, 0.25, 0.45, 0.15];
      descriptions = narrativePresets.find((x) => x.id === "finanzas")
        ?.descriptions ?? [
        "Hook & Contraste",
        "El Mapa / La Empatía",
        "El Núcleo (La Carne)",
        "Cierre & Identidad",
      ];
    }
    const WPM = 150;
    return w.map((pct, i) => ({
      label: descriptions[i] ?? `Acto ${i + 1}`,
      pct: pct * 100,
      min: totalMin * pct,
      words: Math.round(totalMin * pct * WPM),
    }));
  }, [
    lib.swStructure,
    lib.swNarrativePreset,
    lib.swFragmentWeights,
    minutes,
    narrativePresets,
  ]);

  /** Copys de fragmentación acoplados a “Estructura de escenas” (no mezclar 4 actos y 5 bloques en la misma etiqueta). */
  const structureSequentialCopy = useMemo(() => {
    if (lib.swStructure === "four_act") {
      return {
        optionLabel:
          "Por partes: un fragmento por acto (4 fragmentos) + estado completado",
        helperSequential:
          "Con «4 actos» arriba, el guion se divide en cuatro fragmentos (uno por acto). Cada Start step genera un fragmento (o el primero pendiente si eliges automático). Marca Completado cuando valides el texto antes del siguiente.",
        weightsIntro:
          "Los pesos reparten los minutos del pipeline entre los cuatro fragmentos. Vacío = defectos del backend para 4 actos; otra plantilla = otra fila de números aquí.",
      };
    }
    if (lib.swStructure === "default_five_blocks") {
      return {
        optionLabel:
          "Por partes: un fragmento por bloque (5 fragmentos) + estado completado",
        helperSequential:
          "Con «5 bloques» arriba, el guion se divide en cinco fragmentos (uno por bloque). Cada Start step genera un fragmento (o el primero pendiente si eliges automático). Marca Completado cuando valides el texto antes del siguiente.",
        weightsIntro:
          "Los pesos reparten los minutos del pipeline entre los cinco fragmentos. Vacío = defectos del backend para 5 bloques; otra plantilla = otra fila de números aquí.",
      };
    }
    return {
      optionLabel:
        "Por partes según Estructura de escenas (4 actos o 5 bloques): un fragmento por parte + estado completado",
      helperSequential:
        "El número de fragmentos coincide con «Estructura de escenas»: cuatro si eliges 4 actos, cinco si eliges 5 bloques. Cada Start step genera un fragmento (o el primero pendiente si eliges automático). Marca Completado cuando valides el texto antes del siguiente.",
      weightsIntro:
        "Los pesos reparten los minutos entre tantos fragmentos como marque la estructura. Vacío = defectos del backend para esa estructura.",
    };
  }, [lib.swStructure]);

  const loadFragState = useCallback(async () => {
    if (lib.swChunking !== "sequential_fragments") return;
    try {
      const r = await fetch(
        `/api/script-fragmentation?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) return;
      const j = (await r.json()) as {
        exists?: boolean;
        state?: { steps?: { id: string; label: string; status: string }[] };
      };
      setFragExists(!!j.exists);
      const st = j.state?.steps;
      setFragSteps(Array.isArray(st) ? st : []);
    } catch {
      setFragExists(false);
      setFragSteps([]);
    }
  }, [workApplied, lib.swChunking]);

  useEffect(() => {
    void loadFragState();
  }, [loadFragState, scriptStepState, workApplied]);

  const loadScript = useCallback(async () => {
    const r = await fetch(
      `/api/script?work=${encodeURIComponent(workApplied)}`,
    );
    if (!r.ok) return;
    const j = (await r.json()) as {
      text?: string;
      structured?: Record<string, unknown>;
    };
    setScriptText(j.text ?? "");
  }, [workApplied]);

  useEffect(() => {
    void loadScript();
  }, [loadScript, scriptStepState, workApplied]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [dRes, mRes] = await Promise.all([
          fetch("/api/llm/defaults"),
          fetch("/api/ollama/models"),
        ]);
        const d = (await dRes.json()) as LlmDefaultsResponse;
        const mj = (await mRes.json()) as {
          ok: boolean;
          models?: { name: string }[];
          error?: string;
        };
        if (cancelled) return;
        setLlmDefaults(d);
        const names =
          mj.ok && mj.models?.length
            ? mj.models.map((x) => x.name).filter(Boolean)
            : [...FALLBACK_OLLAMA_MODELS];
        setOllamaNames(names);
        setOllamaListHint(
          mj.ok ? null : (mj.error ?? "No se pudo conectar con Ollama"),
        );
        if (!defaultsAppliedRef.current) {
          defaultsAppliedRef.current = true;
          setModel((prev) => {
            if (prev.trim()) return prev;
            const p =
              (d.llm_provider || "ollama").toLowerCase().trim() || "ollama";
            if (p === "openai") return d.openai_model || "";
            return d.ollama_model || "";
          });
        }
      } catch {
        if (!cancelled) {
          setOllamaNames([...FALLBACK_OLLAMA_MODELS]);
          setOllamaListHint("Error de red al cargar modelos");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setModel]);

  const useOpenAiModelField = provider === "openai";

  const ollamaSelectOptions = useMemo(() => {
    const sorted = [...ollamaNames].sort((a, b) => a.localeCompare(b));
    if (model.trim() && !sorted.includes(model)) {
      sorted.push(model);
      sorted.sort((a, b) => a.localeCompare(b));
    }
    return sorted;
  }, [ollamaNames, model]);

  const lockReason =
    scriptStepState === "running"
      ? "Generando guion con el LLM…"
      : locked
        ? "Guion generado (guion.txt, pipeline/script.txt y pipeline/script.json con texto TTS + B-roll por sección)."
        : null;

  return (
    <div className="space-y-3">
      {lockReason ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
          <span className="font-semibold">Bloqueado.</span> {lockReason} Para
          cambiar inputs o regenerar desde cero usa <strong>Reset</strong> en la
          pipeline.
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
        <span className="font-semibold text-slate-900">Script Writer</span> ensambla
        la plantilla del <strong>Catálogo Prompt</strong> (base narrativa y voz), este{" "}
        <strong>template de Script Writer</strong> (ritmo, densidad, estructura) y el bloque
        de <strong>formato técnico</strong> del pipeline (OUTLINE/GUIÓN, <code className="rounded bg-white px-1">[CATEGORIA]</code>, <code className="rounded bg-white px-1">[B-ROLL]</code>
        , stock) común a todas las sesiones. Al ejecutar el paso, el motor une todo; la
        sesión vive en{" "}
        <code className="rounded bg-white px-1">pipeline/prompt.json</code>.
      </div>

      <div
        className={`rounded-2xl border border-slate-200 bg-white p-4 ring-1 ring-slate-100 ${locked ? "opacity-95" : ""}`}
      >
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Catálogo · template de Script Writer
        </div>
        <fieldset
          disabled={locked}
          className="mt-3 min-w-0 space-y-3 border-0 p-0"
        >
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div className="min-w-[260px] flex-1">
              <Label>Template</Label>
              <Select
                value={lib.scriptWriterTemplateId}
                onChange={async (e) => {
                  const id = e.target.value;
                  lib.setScriptWriterTemplateId(id);
                  if (!id) return;
                  await lib.applyTemplateFromApi(id);
                }}
              >
                <option value="">(nuevo template)</option>
                {lib.scriptWriterTemplates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex flex-wrap gap-2">
              <Btn
                type="button"
                className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                onClick={() =>
                  run("Recargar templates SW", async () => {
                    await lib.loadScriptWriterTemplates();
                  })
                }
              >
                Reload
              </Btn>
              <Btn
                type="button"
                className="bg-slate-900 text-white hover:bg-slate-800"
                disabled={!lib.swName.trim()}
                onClick={() =>
                  run("Guardar template Script Writer", async () => {
                    await lib.saveTemplate();
                  })
                }
              >
                Save
              </Btn>
              <Btn
                type="button"
                className="bg-white text-rose-700 ring-1 ring-rose-200 hover:bg-rose-50 disabled:opacity-40"
                disabled={!lib.scriptWriterTemplateId}
                onClick={() =>
                  run("Eliminar template Script Writer", async () => {
                    if (!lib.scriptWriterTemplateId) return;
                    if (!confirm("¿Eliminar este template de Script Writer?"))
                      return;
                    await lib.deleteTemplate();
                  })
                }
              >
                Delete
              </Btn>
            </div>
          </div>

          <div>
            <Label>Nombre</Label>
            <Input
              value={lib.swName}
              onChange={(e) => lib.setSwName(e.target.value)}
              placeholder="Ej: Long-form finanzas · ritmo documental"
            />
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <Label>Ritmo (VO)</Label>
              <Select
                value={lib.swPacing}
                onChange={(e) =>
                  lib.setSwPacing(e.target.value as typeof lib.swPacing)
                }
              >
                <option value="">(sin override: hereda de la plantilla Prompt)</option>
                <option value="short">Corto / rápido</option>
                <option value="mixed">Mixto</option>
                <option value="long">Largo / documental</option>
              </Select>
            </div>
            <div>
              <Label>Densidad de datos</Label>
              <Select
                value={lib.swDataDensity}
                onChange={(e) =>
                  lib.setSwDataDensity(
                    e.target.value as typeof lib.swDataDensity,
                  )
                }
              >
                <option value="">(por defecto)</option>
                <option value="low">Baja (historia / metáfora)</option>
                <option value="medium">Media</option>
                <option value="high">Alta (cifras, series temporales)</option>
              </Select>
            </div>
            <div>
              <Label>Estructura de escenas</Label>
              <Select
                value={lib.swStructure}
                onChange={(e) => {
                  const v = e.target.value as typeof lib.swStructure;
                  lib.setSwStructure(v);
                  if (v !== "four_act") lib.setSwNarrativePreset("");
                }}
              >
                <option value="">(por defecto: 5 bloques)</option>
                <option value="default_five_blocks">
                  5 bloques (intro + 3 pilares + cierre)
                </option>
                <option value="four_act">
                  4 actos (hook → promesa → cuerpo → cierre)
                </option>
              </Select>
            </div>
          </div>

          {lib.swStructure === "four_act" ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                Reparto orientativo (4 actos)
              </div>
              <p className="mt-1 text-[11px] leading-snug text-slate-600">
                Elige una <strong>categoría</strong> para fijar los{" "}
                <strong>pesos %</strong> del tiempo total. Si cambias la{" "}
                <strong>Duración orientativa</strong> más abajo, los porcentajes
                se mantienen y solo se recalculan minutos y palabras (~150/min).
              </p>
              <div className="mt-3 grid gap-3 lg:grid-cols-3">
                <div>
                  <Label>Categoría narrativa</Label>
                  <Select
                    value={lib.swNarrativePreset}
                    onChange={(e) => {
                      const v = e.target.value as ScriptWriterNarrativePreset;
                      if (v === "") {
                        lib.setSwNarrativePreset("");
                        lib.setSwFragmentWeights("");
                        return;
                      }
                      if (v === "custom") {
                        lib.setSwNarrativePreset("custom");
                        return;
                      }
                      const p = narrativePresets.find((x) => x.id === v);
                      lib.setSwNarrativePreset(v);
                      if (p?.weights?.length === 4)
                        lib.setSwFragmentWeights(p.weights.join(", "));
                    }}
                  >
                    <option value="">Seleccione categoría</option>
                    {narrativePresets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                    <option value="custom">
                      Personalizado (editar pesos en fragmentación)
                    </option>
                  </Select>
                </div>
                <div className="lg:col-span-2 overflow-x-auto">
                  {fourActPreview && fourActPreview.length === 4 ? (
                    <table className="w-full min-w-[340px] border-collapse text-left text-[11px]">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-500">
                          <th className="py-1 pr-2 font-medium">Acto</th>
                          <th className="py-1 pr-2 font-medium">Segmento</th>
                          <th className="py-1 pr-2 font-medium">Peso</th>
                          <th className="py-1 pr-2 font-medium">Min</th>
                          <th className="py-1 font-medium">
                            Palabras (~150 wpm)
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {fourActPreview.map((row, i) => (
                          <tr
                            key={i}
                            className="border-b border-slate-100 text-slate-800"
                          >
                            <td className="py-1 pr-2 font-mono text-slate-600">
                              {["I", "II", "III", "IV"][i]}
                            </td>
                            <td className="py-1 pr-2">{row.label}</td>
                            <td className="py-1 pr-2 font-mono">
                              {row.pct.toFixed(0)}%
                            </td>
                            <td className="py-1 pr-2 font-mono">
                              {row.min.toFixed(1)}
                            </td>
                            <td className="py-1 font-mono">~{row.words}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : null}
                  <p className="mt-2 text-[10px] leading-snug text-slate-500">
                    Vista previa usando la duración del pipeline (
                    {Number.isFinite(minutes) && minutes > 0 ? minutes : 20}{" "}
                    min).
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          <div className="max-w-xl">
            <Label>Fragmentación (chunking)</Label>
            <Select
              value={lib.swChunking}
              onChange={(e) =>
                lib.setSwChunking(e.target.value as typeof lib.swChunking)
              }
            >
              <option value="">Seleccione el modo de fragmentación</option>
              <option value="full_pass">
                Guion completo en una pasada (pipeline)
              </option>
              <option value="outline_act1_only">
                Solo OUTLINE + primer bloque (~0–5 min VO); marcador
                &lt;&lt;&lt; FIN_FRAGMENTO_1 &gt;&gt;&gt;
              </option>
              <option value="sequential_fragments">
                {structureSequentialCopy.optionLabel}
              </option>
            </Select>
            {lib.swChunking === "outline_act1_only" ? (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Una pasada corta; luego sigues en otra ejecución. El modelo no
                puede esperar en tiempo real.
              </p>
            ) : lib.swChunking === "sequential_fragments" ? (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                {structureSequentialCopy.helperSequential}
              </p>
            ) : lib.swChunking === "full_pass" ? (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Por defecto el pipeline intenta el guion completo (puede usar
                modo interno por etapas si está configurado).
              </p>
            ) : (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Seleccione cómo generar el guion: una pasada, solo el primer
                bloque o por fragmentos acoplados a «Estructura de escenas».
              </p>
            )}
          </div>

          {lib.swChunking === "sequential_fragments" ? (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 px-3 py-3 text-xs text-indigo-950">
              <div className="font-semibold uppercase tracking-wide text-indigo-900/90">
                Progreso por fragmentos
              </div>
              <p className="mt-1 text-[11px] leading-snug text-indigo-900/85">
                {structureSequentialCopy.weightsIntro}
              </p>
              <div className="mt-2">
                <Label>Pesos de minutos por fragmento (opcional)</Label>
                <TextArea
                  value={lib.swFragmentWeights}
                  onChange={(e) => {
                    lib.setSwFragmentWeights(e.target.value);
                    if (lib.swStructure === "four_act")
                      lib.setSwNarrativePreset("custom");
                  }}
                  className="min-h-[52px] font-mono text-[11px]"
                  placeholder={
                    lib.swStructure === "four_act"
                      ? "Ej. Nick-like 4 actos: 0.14, 0.18, 0.46, 0.22"
                      : "Ej. 5 bloques: 0.10, 0.20, 0.22, 0.22, 0.26"
                  }
                  disabled={locked}
                />
                <p className="mt-1 text-[10px] leading-snug text-indigo-900/75">
                  Un número por fragmento en orden (hook→…→cierre). Pueden ser
                  proporciones cualquiera: se <strong>normalizan</strong> a suma
                  1. Guarda el template tras editar.
                </p>
              </div>
              <div className="mt-2 flex flex-wrap items-end gap-2">
                <div className="min-w-[220px] flex-1">
                  <Label>Qué fragmento genera “Start step”</Label>
                  <Select
                    value={
                      scriptFragmentIndex === null
                        ? ""
                        : String(scriptFragmentIndex)
                    }
                    onChange={(e) => {
                      const v = e.target.value;
                      setScriptFragmentIndex(v === "" ? null : Number(v));
                    }}
                  >
                    <option value="">Automático (primer pendiente)</option>
                    {Array.from(
                      {
                        length:
                          fragSteps.length > 0
                            ? fragSteps.length
                            : lib.swStructure === "four_act"
                              ? 4
                              : 5,
                      },
                      (_, i) => (
                        <option key={i} value={String(i)}>
                          Fragmento {i}
                          {fragSteps[i]?.label
                            ? ` · ${fragSteps[i].label}`
                            : ""}
                        </option>
                      ),
                    )}
                  </Select>
                  <p className="mt-1 text-[10px] leading-snug text-indigo-900/80">
                    <strong>Automático:</strong> tras cada Start step el servidor elige el siguiente fragmento que siga{" "}
                    <em>pending</em>; el texto del fragmento anterior queda guardado en disco y no tienes que cambiar el índice a
                    mano. <strong>Si eliges un número fijo</strong> (p. ej. Fragmento 0), cada Start step vuelve a generar ese
                    mismo índice hasta que cambies a otro o a Automático. Marcar <em>Completado</em> solo ordena tu revisión; no
                    es obligatorio para pasar al siguiente en modo Automático.
                  </p>
                </div>
                <Btn
                  type="button"
                  className="bg-white text-indigo-900 ring-1 ring-indigo-200 hover:bg-indigo-50"
                  onClick={() => void loadFragState()}
                >
                  Refrescar lista
                </Btn>
                <Btn
                  type="button"
                  className="bg-white text-rose-800 ring-1 ring-rose-200 hover:bg-rose-50"
                  onClick={() =>
                    run("Reiniciar fragmentación", async () => {
                      if (
                        !confirm(
                          "¿Borrar estado y chunks guardados en esta sesión?",
                        )
                      )
                        return;
                      await postJson(`/api/script-fragmentation/reset`, {
                        work: workApplied,
                      });
                      setScriptFragmentIndex(null);
                      await loadFragState();
                      await refreshPipeline();
                    })
                  }
                >
                  Reiniciar fragmentación
                </Btn>
              </div>
              {!fragExists ? (
                <p className="mt-2 text-[11px] text-indigo-800/90">
                  Aún no hay estado en disco: tras el primer Start step aparecerán
                  los pasos con su estado (pending / generated / done).
                </p>
              ) : (
                <ul className="mt-3 space-y-2 border-t border-indigo-200/80 pt-3">
                  {fragSteps.map((s, i) => (
                    <li
                      key={`${s.id}-${i}`}
                      className="flex flex-wrap items-center gap-2"
                    >
                      <span className="w-6 font-mono text-[11px] text-indigo-700">
                        {i}
                      </span>
                      <span className="min-w-[120px] flex-1 font-medium">
                        {s.label}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] uppercase tracking-wide ring-1 ring-indigo-200">
                        {s.status}
                      </span>
                      <label className="flex cursor-pointer items-center gap-1 text-[11px]">
                        <input
                          type="checkbox"
                          className="rounded border-indigo-300"
                          checked={s.status === "done"}
                          disabled={locked}
                          onChange={(e) =>
                            run(
                              s.status === "done"
                                ? "Marcar fragmento pendiente"
                                : "Marcar fragmento completado",
                              async () => {
                                await patchJson(`/api/script-fragmentation`, {
                                  work: workApplied,
                                  index: i,
                                  complete: e.target.checked,
                                });
                                await loadFragState();
                                await refreshPipeline();
                              },
                            )
                          }
                        />
                        Completado
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}

          <div>
            <Label>Instrucciones sistema (overlay)</Label>
            <TextArea
              value={lib.swSystem}
              onChange={(e) => lib.setSwSystem(e.target.value)}
              className="min-h-[72px] text-xs"
              placeholder="Opcional: reglas extra solo para la generación del guion (se añaden al system del LLM tras el template de Prompt)."
            />
          </div>
          <div>
            <Label>Instrucciones usuario (overlay)</Label>
            <TextArea
              value={lib.swUser}
              onChange={(e) => lib.setSwUser(e.target.value)}
              className="min-h-[72px] text-xs"
              placeholder="Opcional: preferencias de formato, ejemplos a evitar, compliance…"
            />
          </div>
        </fieldset>
      </div>

      <fieldset disabled={locked} className="min-w-0 space-y-3 border-0 p-0">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label>Keywords (coma)</Label>
            <Input
              value={kw}
              onChange={(e) => setKw(e.target.value)}
              placeholder="tema, ángulo, intención…"
            />
          </div>
          <div className="sm:col-span-2">
            <Label>Contexto</Label>
            <TextArea
              value={ctx}
              onChange={(e) => setCtx(e.target.value)}
              placeholder="Público, tono, datos que deben aparecer…"
            />
          </div>
          <div>
            <Label>Idioma</Label>
            <Select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="es">es</option>
              <option value="en">en</option>
            </Select>
          </div>
          <div>
            <Label>Duración orientativa (min)</Label>
            <Input
              type="number"
              step={0.5}
              min={1}
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            />
          </div>
          <div>
            <Label>Proveedor LLM</Label>
            <Select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="">(usar .env)</option>
              <option value="ollama">ollama</option>
              <option value="openai">openai-compatible (API futura)</option>
            </Select>
          </div>
          <div>
            <Label>Modelo</Label>
            {useOpenAiModelField ? (
              <Input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={llmDefaults?.openai_model?.trim() || "gpt-4o-mini"}
              />
            ) : (
              <>
                <Select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  <option value="">Predeterminado (.env)</option>
                  {ollamaSelectOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </Select>
                {ollamaListHint ? (
                  <p className="mt-1 text-[11px] leading-snug text-amber-800">
                    Lista local no disponible ({ollamaListHint}). Mostrando
                    modelos de respaldo; reinicia Ollama o recarga la página.
                  </p>
                ) : null}
              </>
            )}
            {!useOpenAiModelField ? (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Valor inicial según{" "}
                <code className="rounded bg-slate-100 px-1">OLLAMA_MODEL</code>{" "}
                en <code className="rounded bg-slate-100 px-1">.env</code>.
                Vacío = usar lo configurado en el servidor.
              </p>
            ) : (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Para cuando conectes una API compatible (OpenAI, Anthropic vía
                proxy, etc.). Vacío ={" "}
                <code className="rounded bg-slate-100 px-1">OPENAI_MODEL</code>{" "}
                del <code className="rounded bg-slate-100 px-1">.env</code>.
              </p>
            )}
          </div>
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Salida · guion.txt + pipeline/script.json
        </div>
        <Btn
          type="button"
          className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
          onClick={() => void loadScript()}
        >
          Recargar desde disco
        </Btn>
      </div>

      <fieldset disabled={locked} className="min-w-0 space-y-2 border-0 p-0">
        <Label>Texto del guion</Label>
        <TextArea
          value={scriptText}
          onChange={(e) => setScriptText(e.target.value)}
          className="min-h-[280px] font-mono text-xs"
          placeholder="Tras Start step aparecerá aquí el guion generado; puedes editarlo y guardar si el paso no está bloqueado."
        />
        <div className="flex flex-wrap gap-2">
          <Btn
            className="bg-slate-900 text-white hover:bg-slate-800"
            onClick={() =>
              run("Guardar guion", async () => {
                await putJson(`/api/script`, {
                  work: workApplied,
                  text: scriptText,
                });
                await loadScript();
              })
            }
          >
            Guardar en sesión
          </Btn>
          <span className="self-center text-[11px] text-slate-500">
            Guarda texto plano en{" "}
            <code className="rounded bg-slate-100 px-1">guion.txt</code>,
            sincroniza{" "}
            <code className="rounded bg-slate-100 px-1">
              pipeline/script.txt
            </code>{" "}
            y actualiza{" "}
            <code className="rounded bg-slate-100 px-1">
              pipeline/script.json
            </code>{" "}
            (TTS + secciones / B-roll).
          </span>
        </div>
      </fieldset>
    </div>
  );
}
