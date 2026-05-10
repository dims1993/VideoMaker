import { useCallback, useEffect, useMemo, useState } from "react";
import { Btn, Card, Input, Label, Select, TextArea } from "./components/ui";
import { deleteReq, postJson, putJson, readApiError } from "./services/api";
import type { Session } from "./types";
import { Sidebar } from "./components/common/Sidebar";
import { AnalyzeCard } from "./features/analyze";
import { CreatePipelineCard } from "./features/create";
import type { PipelineState } from "./types/pipeline";

function initialWorkFromUrl(): string {
  try {
    const w = new URLSearchParams(window.location.search).get("work");
    return w && w.trim() ? w.trim() : "output/ui_session";
  } catch {
    return "output/ui_session";
  }
}

export default function App() {
  const [work, setWork] = useState(initialWorkFromUrl);
  const [workApplied, setWorkApplied] = useState(initialWorkFromUrl);
  const [session, setSession] = useState<Session | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"analyze" | "create">("create");
  const [pipelineState, setPipelineState] = useState<PipelineState | null>(null);
  const [openPipelineStepId, setOpenPipelineStepId] = useState<string | null>(null);

  const [kw, setKw] = useState("motivación, hábitos, enfoque");
  const [ctx, setCtx] = useState("");
  const [lang, setLang] = useState("es");
  const [minutes, setMinutes] = useState(10);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [previewText, setPreviewText] = useState("Hola, esta es una prueba de voz antes de narrar el vídeo.");
  const [preset, setPreset] = useState("xtts_v2_es");
  const [maxChars, setMaxChars] = useState(900);
  const [maxSeg, setMaxSeg] = useState(0);
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptData, setPromptData] = useState<{ system: string; user: string } | null>(null);
  const [scriptEditorOpen, setScriptEditorOpen] = useState(false);
  const [scriptEditText, setScriptEditText] = useState("");
  const [promptPresets, setPromptPresets] = useState<{ id: string; name: string }[]>([]);
  const [promptSelectedId, setPromptSelectedId] = useState<string | null>(null);
  const [promptSystemExtra, setPromptSystemExtra] = useState("");
  const [promptUserExtra, setPromptUserExtra] = useState("");
  const [newPresetName, setNewPresetName] = useState("");

  const loadPromptPresets = useCallback(async () => {
    try {
      const r = await fetch("/api/prompt-presets");
      if (!r.ok) return;
      const j = (await r.json()) as { presets: { id: string; name: string }[]; selected_id: string | null };
      setPromptPresets(j.presets ?? []);
      const sid = j.selected_id;
      setPromptSelectedId(sid);
      if (sid) {
        const pr = await fetch(`/api/prompt-preset?preset_id=${encodeURIComponent(sid)}`);
        if (pr.ok) {
          const p = (await pr.json()) as { system_extra?: string; user_extra?: string };
          setPromptSystemExtra(p.system_extra ?? "");
          setPromptUserExtra(p.user_extra ?? "");
        }
      } else {
        setPromptSystemExtra("");
        setPromptUserExtra("");
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadPromptPresets();
  }, [loadPromptPresets]);

  const refresh = useCallback(async () => {
    setErr(null);
    const r = await fetch(`/api/session?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) {
      setErr(await r.text());
      setSession(null);
      return;
    }
    setSession(await r.json());
  }, [workApplied]);

  const refreshPipeline = useCallback(async () => {
    try {
      const r = await fetch(`/api/pipeline/state?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) return;
      setPipelineState((await r.json()) as PipelineState);
    } catch {
      /* ignore */
    }
  }, [workApplied]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const id = setInterval(() => void refresh(), 2000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    void refreshPipeline();
    const id = setInterval(() => void refreshPipeline(), 2000);
    return () => clearInterval(id);
  }, [refreshPipeline]);

  const statusLine = useMemo(() => {
    if (!session) return "";
    const s = session.status;
    return `${s.state}${s.step ? ` · ${s.step}` : ""}${s.detail ? ` — ${s.detail}` : ""}`;
  }, [session]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    setScriptEditorOpen(false);
  }, [workApplied]);

  const openScriptEditor = async () => {
    setErr(null);
    try {
      const r = await fetch(`/api/script?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) throw new Error(await readApiError(r));
      const j = (await r.json()) as { text: string };
      setScriptEditText(j.text);
      setScriptEditorOpen(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        session={session}
        statusLine={statusLine}
        work={work}
        setWork={setWork}
        applyWork={() => setWorkApplied(work.trim() || "output/ui_session")}
      />

      <main className="min-h-screen pl-[280px]">
        <div className="p-6">
          {err ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">{err}</div>
          ) : null}
          {busy ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">Enviando: {busy}…</div>
          ) : null}

          {activeTab === "analyze" ? (
            <AnalyzeCard workApplied={workApplied} session={session} run={run} />
          ) : null}

          {activeTab === "create" ? (
            <CreatePipelineCard
              pipelineState={pipelineState}
              openPipelineStepId={openPipelineStepId}
              onOpenStep={(id) => setOpenPipelineStepId(id)}
              onCloseStep={() => setOpenPipelineStepId(null)}
              workApplied={workApplied}
              run={run}
              refreshPipeline={refreshPipeline}
              session={session}
              busy={busy}
              kw={kw}
              setKw={setKw}
              ctx={ctx}
              setCtx={setCtx}
              lang={lang}
              setLang={setLang}
              minutes={minutes}
              setMinutes={setMinutes}
              provider={provider}
              setProvider={setProvider}
              model={model}
              setModel={setModel}
              preset={preset}
              setPreset={setPreset}
              previewText={previewText}
              setPreviewText={setPreviewText}
              maxChars={maxChars}
              setMaxChars={setMaxChars}
              maxSeg={maxSeg}
              setMaxSeg={setMaxSeg}
            />
          ) : null}

          <div className={activeTab === "create" ? "space-y-6" : "hidden"}>
          {false ? (
          <Card
            title="1 · Guion"
            subtitle="Keywords + LLM (OpenAI compatible u Ollama según .env). Los minutos son una referencia orientativa, no un límite rígido."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label>Keywords (separadas por coma)</Label>
                <Input value={kw} onChange={(e) => setKw(e.target.value)} />
              </div>
              <div className="sm:col-span-2">
                <Label>Contexto</Label>
                <TextArea value={ctx} onChange={(e) => setCtx(e.target.value)} />
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
                <Input type="number" step={0.5} min={1} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
                <p className="mt-1 text-[11px] leading-snug text-slate-500">
                  Guía orientativa (~10 min de narración / tres actos); el modelo prioriza ~1 500 palabras y estructura en prompts.
                </p>
              </div>
              <div>
                <Label>Proveedor (vacío = .env)</Label>
                <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="">(usar .env)</option>
                  <option value="ollama">ollama</option>
                  <option value="openai">openai-compatible</option>
                </Select>
              </div>
              <div>
                <Label>Modelo (opcional)</Label>
                <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini / llama3.2:latest" />
              </div>
            </div>

            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4">
              <Label>Plantillas de prompt (ampliación opcional)</Label>
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Se añaden al system y user que ya genera Videomaker (tres actos, B-roll, etc.). Úsalas para refinar sin
                reemplazar la base. Las plantillas se guardan en la raíz del repo:{" "}
                <code className="rounded bg-white px-1">prompt_presets.json</code>.
              </p>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <div className="min-w-[220px] flex-1">
                  <Label>Seleccionar plantilla</Label>
                  <Select
                    value={promptSelectedId ?? ""}
                    disabled={!!busy}
                    onChange={async (e) => {
                      const id = e.target.value;
                      setErr(null);
                      try {
                        if (!id) {
                          setPromptSelectedId(null);
                          setPromptSystemExtra("");
                          setPromptUserExtra("");
                          await postJson("/api/prompt-preset/select", { id: null });
                          return;
                        }
                        const pr = await fetch(`/api/prompt-preset?preset_id=${encodeURIComponent(id)}`);
                        if (!pr.ok) throw new Error(await readApiError(pr));
                        const p = (await pr.json()) as { system_extra?: string; user_extra?: string };
                        setPromptSelectedId(id);
                        setPromptSystemExtra(p.system_extra ?? "");
                        setPromptUserExtra(p.user_extra ?? "");
                        await postJson("/api/prompt-preset/select", { id });
                      } catch (ex) {
                        setErr(ex instanceof Error ? ex.message : String(ex));
                      }
                    }}
                  >
                    <option value="">— Solo prompt por defecto —</option>
                    {promptPresets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Btn
                    className="bg-white px-3 py-1.5 text-xs font-medium text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                    disabled={!!busy || !newPresetName.trim()}
                    onClick={() =>
                      run("guardar plantilla", async () => {
                        await postJson("/api/prompt-preset", {
                          name: newPresetName.trim(),
                          system_extra: promptSystemExtra,
                          user_extra: promptUserExtra,
                        });
                        setNewPresetName("");
                        await loadPromptPresets();
                      })
                    }
                  >
                    Guardar como nueva
                  </Btn>
                  <Btn
                    className="bg-white px-3 py-1.5 text-xs font-medium text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40"
                    disabled={!!busy || !promptSelectedId}
                    onClick={() =>
                      run("actualizar plantilla", async () => {
                        await putJson("/api/prompt-preset", {
                          id: promptSelectedId,
                          system_extra: promptSystemExtra,
                          user_extra: promptUserExtra,
                        });
                        await loadPromptPresets();
                      })
                    }
                  >
                    Actualizar seleccionada
                  </Btn>
                  <Btn
                    className="bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-900 ring-1 ring-rose-200 hover:bg-rose-100 disabled:opacity-40"
                    disabled={!!busy || !promptSelectedId}
                    onClick={() =>
                      run("eliminar plantilla", async () => {
                        if (!promptSelectedId || !confirm("¿Eliminar esta plantilla de prompt?")) return;
                        await deleteReq(`/api/prompt-preset?preset_id=${encodeURIComponent(promptSelectedId)}`);
                        setPromptSelectedId(null);
                        setPromptSystemExtra("");
                        setPromptUserExtra("");
                        await loadPromptPresets();
                      })
                    }
                  >
                    Eliminar
                  </Btn>
                </div>
              </div>
              <div className="mt-2">
                <Label>Nombre para “Guardar como nueva”</Label>
                <Input
                  value={newPresetName}
                  onChange={(e) => setNewPresetName(e.target.value)}
                  placeholder="Ej. YouTube largo · B-roll cada 2 frases"
                  className="max-w-xl"
                />
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>Texto extra → system</Label>
                  <textarea
                    value={promptSystemExtra}
                    onChange={(e) => setPromptSystemExtra(e.target.value)}
                    spellCheck={lang === "es"}
                    className="mt-1 min-h-[140px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-relaxed text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/25"
                  />
                </div>
                <div>
                  <Label>Texto extra → user</Label>
                  <textarea
                    value={promptUserExtra}
                    onChange={(e) => setPromptUserExtra(e.target.value)}
                    spellCheck={lang === "es"}
                    className="mt-1 min-h-[140px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-relaxed text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/25"
                  />
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Btn
                className="bg-slate-200 text-slate-900 hover:bg-slate-300"
                disabled={!!busy}
                title="Construye los prompts en el servidor y los muestra. No llama al LLM ni escribe archivos."
                onClick={() =>
                  run("prompt", async () => {
                    const j = await postJson<{ system: string; user: string }>("/api/prompt-preview", {
                      work: workApplied,
                      keywords: kw,
                      context: ctx,
                      lang,
                      minutes,
                      system_extra: promptSystemExtra,
                      user_extra: promptUserExtra,
                    });
                    setPromptData(j);
                    setPromptOpen(true);
                  })
                }
              >
                Previsualizar prompt
              </Btn>
              <Btn
                className="bg-emerald-600 text-white hover:bg-emerald-500"
                disabled={!!busy}
                onClick={() =>
                  run("guion", async () => {
                    await postJson("/api/generate-script", {
                      work: workApplied,
                      keywords: kw,
                      context: ctx,
                      lang,
                      minutes,
                      provider,
                      model,
                      system_extra: promptSystemExtra,
                      user_extra: promptUserExtra,
                    });
                  })
                }
              >
                Generar guion.txt
              </Btn>
              {session?.has_script ? (
                <Btn
                  className="bg-white text-slate-900 ring-2 ring-emerald-500/40 hover:bg-emerald-50"
                  disabled={!!busy}
                  onClick={() => void openScriptEditor()}
                >
                  Ver y editar guion
                </Btn>
              ) : null}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-500">
              <span className="font-semibold text-slate-600">Previsualizar prompt:</span> muestra los textos <em>system</em> y{" "}
              <em>user</em> que se mandarían al modelo (según keywords, contexto, idioma y minutos).{" "}
              <strong>No consume API</strong> ni crea <code className="rounded bg-slate-100 px-1">guion.txt</code>. Sirve para revisar instrucciones antes de gastar tokens.
            </p>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              <span className="font-semibold text-slate-600">Página HTML clásica:</span> abre el guion en una pestaña aparte, solo lectura, útil si prefieres copiar con formato simple.{" "}
              <button
                type="button"
                className="font-medium text-emerald-700 underline decoration-emerald-300 underline-offset-2 hover:text-emerald-900"
                disabled={!session?.has_script}
                onClick={() => window.open(`/view-script?work=${encodeURIComponent(workApplied)}`, "_blank")}
              >
                Abrir vista solo lectura
              </button>
              {!session?.has_script ? <span className="text-slate-400"> (genera un guion antes)</span> : null}
            </p>
            {scriptEditorOpen ? (
              <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-800">Editor · guion.txt (+ script.json)</span>
                  <Btn className="bg-white px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setScriptEditorOpen(false)}>
                    Cerrar
                  </Btn>
                </div>
                <textarea
                  value={scriptEditText}
                  onChange={(e) => setScriptEditText(e.target.value)}
                  spellCheck={lang === "es"}
                  className="mt-3 min-h-[280px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-relaxed text-slate-900 shadow-inner outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/25"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Btn
                    className="bg-emerald-600 text-white hover:bg-emerald-500"
                    disabled={!!busy}
                    onClick={() =>
                      run("guardar guion", async () => {
                        await putJson("/api/script", { work: workApplied, text: scriptEditText });
                        await refresh();
                        setScriptEditorOpen(false);
                      })
                    }
                  >
                    Guardar cambios
                  </Btn>
                  <span className="self-center text-[11px] text-slate-500">
                    Guarda guion.txt y actualiza pipeline/script.json (texto TTS + secciones / B-roll).
                  </span>
                </div>
              </div>
            ) : null}
          </Card>
          ) : null}

          {false ? (
          <Card title="Voiceovers generation" subtitle="Sube MP3/WAV, prueba previews y genera la narración completa.">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-sm text-emerald-950">
              Con muestra subida, elige preset <code className="rounded bg-white/80 px-1">xtts_v2_es</code> o{" "}
              <code className="rounded bg-white/80 px-1">xtts_v2_en</code> para clonar.
            </div>
            <details className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2 text-xs text-slate-700">
              <summary className="cursor-pointer font-medium text-slate-800">Mejor clonación (XTTS no es magia)</summary>
              <ul className="mt-2 list-inside list-disc space-y-1.5 text-slate-600">
                <li>
                  Grabación limpia: <strong>sin música ni reverberación fuerte</strong>, una sola voz, ~15–60&nbsp;s suele bastar.
                </li>
                <li>
                  El idioma del <strong>texto generado</strong> debe coincidir con el preset (es/en); si no, el acento suena raro.
                </li>
                <li>
                  Tras subir un MP3 nuevo, la app recorta silencios y normaliza un poco el WAV; si sigue flojo, prueba un WAV más limpio o GPU (
                  <code className="rounded bg-white px-1">TTS_USE_GPU</code> si tienes CUDA).
                </li>
                <li>
                  Ajustes finos del modelo: variables <code className="rounded bg-white px-1">VIDEOMAKER_XTTS_*</code> en{" "}
                  <code className="rounded bg-white px-1">.env</code> (ver <code className="rounded bg-white px-1">.env.example</code>).
                </li>
              </ul>
            </details>
            <div>
              <Label>Archivo de voz (MP3, WAV, …)</Label>
              <input
                type="file"
                accept="audio/*,.mp3,.wav,.m4a"
                className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white hover:file:bg-slate-800"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (!f) return;
                  await run("subir clon", async () => {
                    const fd = new FormData();
                    fd.append("work", workApplied);
                    fd.append("file", f);
                    const r = await fetch("/api/upload-voice-clone", { method: "POST", body: fd });
                    if (!r.ok) throw new Error(await r.text());
                  });
                }}
              />
            </div>
            {session?.has_clone_reference ? (
              <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-slate-500">Muestra activa</div>
                  <audio className="mt-2 w-full" controls src={session?.urls?.clone_reference || ""} />
                </div>
                <Btn
                  className="shrink-0 bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                  disabled={!!busy}
                  onClick={() =>
                    run("quitar clon", async () => {
                      await postJson("/api/clear-voice-clone", { work: workApplied });
                    })
                  }
                >
                  Quitar clon
                </Btn>
              </div>
            ) : null}
            <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label>Voz (preset)</Label>
                <Select value={preset} onChange={(e) => setPreset(e.target.value)}>
                  {session?.voice_presets.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  )) ?? null}
                </Select>
              </div>
              <div className="sm:col-span-2">
                <Label>Texto de prueba</Label>
                <Input value={previewText} onChange={(e) => setPreviewText(e.target.value)} />
              </div>
              <Btn
                className="bg-slate-900 text-white hover:bg-slate-800 sm:col-span-2"
                disabled={!!busy}
                onClick={() =>
                  run("voice preview", async () => {
                    await postJson("/api/voice-preview", { work: workApplied, preset, text: previewText });
                  })
                }
              >
                Generar muestra de voz
              </Btn>
            </div>
            {(session?.voice_previews?.length ?? 0) > 0 ? (
              <div className="space-y-3 border-t border-slate-100 pt-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Muestras recientes</div>
                  <Btn
                    className="bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-900 ring-1 ring-rose-200 hover:bg-rose-100"
                    disabled={!!busy}
                    onClick={() =>
                      run("borrar muestras", async () => {
                        if (!confirm("¿Eliminar todas las muestras de voz (preview_voice*.wav) en esta sesión?")) return;
                        await deleteReq(`/api/voice-previews?work=${encodeURIComponent(workApplied)}`);
                        await refresh();
                      })
                    }
                  >
                    Eliminar todas las muestras
                  </Btn>
                </div>
                {[...(session?.voice_previews ?? [])].reverse().map((v) => (
                  <div key={v.name} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <code className="min-w-0 flex-1 break-all text-[11px] text-slate-600">{v.name}</code>
                      <Btn
                        className="shrink-0 bg-white px-2 py-1 text-[11px] text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"
                        disabled={!!busy}
                        onClick={() =>
                          run("borrar muestra", async () => {
                            await deleteReq(
                              `/api/voice-preview?work=${encodeURIComponent(workApplied)}&name=${encodeURIComponent(v.name)}`,
                            );
                            await refresh();
                          })
                        }
                      >
                        Eliminar
                      </Btn>
                    </div>
                    <audio className="mt-2 w-full" controls src={v.url} />
                  </div>
                ))}
              </div>
            ) : null}
            <div className="border-t border-slate-100 pt-4">
              <Label>Voz para narración completa (guion → narracion.wav)</Label>
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Solo afecta la narración larga. “Automático” usa el clon subido si existe; puedes forzar una muestra de prueba concreta.
              </p>
              <Select
                className="mt-2"
                disabled={!session || !!busy}
                value={
                  (session?.tts_reference?.mode === "preview" && session?.tts_reference?.preview_filename
                    ? session?.tts_reference?.preview_filename
                    : session?.tts_reference?.mode) || "auto"
                }
                onChange={async (e) => {
                  const v = e.target.value;
                  setErr(null);
                  try {
                    if (v === "auto" || v === "clone" || v === "builtin") {
                      await postJson("/api/tts-reference", { work: workApplied, mode: v });
                    } else {
                      await postJson("/api/tts-reference", {
                        work: workApplied,
                        mode: "preview",
                        preview_filename: v,
                      });
                    }
                    await refresh();
                  } catch (err) {
                    setErr(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                <option value="auto">Automático — clon si hay muestra subida; si no, voz integrada</option>
                <option value="clone" disabled={!session?.has_clone_reference}>
                  Solo clon (clone_reference.wav){!session?.has_clone_reference ? " — sube un clon antes" : ""}
                </option>
                <option value="builtin">Solo voz integrada del modelo (sin clon ni muestra)</option>
                {(session?.voice_previews ?? []).map((v) => (
                  <option key={v.name} value={v.name}>
                    Muestra: {v.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <div>
                <Label>Máx. caracteres por fragmento</Label>
                <Input type="number" value={maxChars} onChange={(e) => setMaxChars(Number(e.target.value))} />
              </div>
              <div>
                <Label>Máx. fragmentos (0 = todos)</Label>
                <Input type="number" value={maxSeg} onChange={(e) => setMaxSeg(Number(e.target.value))} />
              </div>
              <Btn
                className="bg-emerald-600 text-white hover:bg-emerald-500 sm:col-span-2"
                disabled={!!busy || !session?.has_script}
                onClick={() =>
                  run("narración", async () => {
                    await postJson("/api/speak-script", {
                      work: workApplied,
                      preset,
                      max_chars: maxChars,
                      max_segments: maxSeg,
                    });
                  })
                }
              >
                Generar narracion.wav
              </Btn>
            </div>
            {(session?.narration_versions?.length ?? 0) > 0 ? (
              <div className="space-y-3 border-t border-slate-100 pt-4">
                <div>
                  <Label>Versión para stock y render</Label>
                  <p className="mt-1 text-[11px] leading-snug text-slate-500">
                    El render y la descarga de stock usan siempre <code className="rounded bg-slate-100 px-1">narracion.wav</code>; aquí eliges qué generación se copia ahí.
                  </p>
                  <Select
                    className="mt-2"
                    disabled={!!busy}
                    value={
                      session?.active_narration ??
                      session?.narration_versions?.find((x) => x.active)?.name ??
                      session?.narration_versions?.[0]?.name ??
                      ""
                    }
                    onChange={(e) => {
                      const name = e.target.value;
                      if (!name) return;
                      void run("elegir narración", async () => {
                        await postJson("/api/narration/select", { work: workApplied, name });
                      });
                    }}
                  >
                    {(session?.narration_versions ?? []).map((n) => (
                      <option key={n.name} value={n.name}>
                        {n.name}
                        {n.active ? " · activa" : ""}
                      </option>
                    ))}
                  </Select>
                </div>
                {session?.has_narration ? (
                  <div>
                    <Label>Narración activa (preview)</Label>
                    <audio className="mt-2 w-full" controls src={session?.urls?.narration || ""} />
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Historial de narraciones</div>
                </div>
                {(session?.narration_versions ?? []).map((nv) => (
                  <div key={nv.name} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <code className="min-w-0 flex-1 break-all text-[11px] text-slate-600">{nv.name}</code>
                      <Btn
                        className="shrink-0 bg-white px-2 py-1 text-[11px] text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"
                        disabled={!!busy}
                        onClick={() =>
                          run("borrar narración", async () => {
                            await deleteReq(
                              `/api/narration?work=${encodeURIComponent(workApplied)}&name=${encodeURIComponent(nv.name)}`,
                            );
                          })
                        }
                      >
                        Eliminar
                      </Btn>
                    </div>
                    <audio className="mt-2 w-full" controls src={nv.url} />
                  </div>
                ))}
              </div>
            ) : session?.has_narration ? (
              <div className="border-t border-slate-100 pt-4">
                <Label>Narración</Label>
                <audio className="mt-2 w-full" controls src={session?.urls?.narration || ""} />
              </div>
            ) : null}
          </Card>
          ) : null}

          </div>
        </div>
      </main>

      {promptOpen && promptData ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" role="dialog">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <span className="font-semibold text-slate-900">Prompt (sin llamar a la API)</span>
              <button type="button" className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" onClick={() => setPromptOpen(false)}>
                Cerrar
              </button>
            </div>
            <div className="grid max-h-[calc(85vh-52px)] gap-0 sm:grid-cols-2">
              <div className="border-b border-slate-100 p-4 sm:border-b-0 sm:border-r">
                <div className="text-xs font-semibold uppercase text-slate-500">System</div>
                <pre className="mt-2 max-h-[50vh] overflow-auto whitespace-pre-wrap text-xs text-slate-800">{promptData.system}</pre>
              </div>
              <div className="p-4">
                <div className="text-xs font-semibold uppercase text-slate-500">User</div>
                <pre className="mt-2 max-h-[50vh] overflow-auto whitespace-pre-wrap text-xs text-slate-800">{promptData.user}</pre>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
