import { useEffect, useRef, useState } from "react";
import { Btn, Input, Label, Select } from "../../../components/ui";
import { postJson } from "../../../services/api";
import type { Session } from "../../../types/session";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

function formatDuration(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function NarrationPlayer({
  url, label, active, onSelect, onDelete,
}: {
  url: string; label: string; active: boolean; onSelect?: () => void; onDelete?: () => void;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [duration, setDuration] = useState<number | null>(null);

  return (
    <div className={`rounded-xl border p-3 transition-colors ${active ? "border-emerald-500/50 bg-emerald-950/30" : "border-slate-600 bg-slate-800 hover:border-slate-500"}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {active && (
            <span className="shrink-0 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold text-white">Activa</span>
          )}
          <span className="truncate text-xs font-medium text-slate-200">{label}</span>
          {duration !== null && <span className="shrink-0 text-[10px] text-slate-400">{formatDuration(duration)}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!active && onSelect && (
            <button className="rounded-lg bg-emerald-700 px-2 py-1 text-[10px] font-medium text-white hover:bg-emerald-600" onClick={onSelect}>Activar</button>
          )}
          {onDelete && (
            <button className="rounded-lg border border-rose-500/50 bg-rose-950/40 px-2 py-1 text-[10px] font-medium text-rose-400 hover:bg-rose-950/70" onClick={onDelete}>Eliminar</button>
          )}
        </div>
      </div>
      <audio ref={audioRef} className="w-full" controls src={url} onLoadedMetadata={(e) => setDuration((e.target as HTMLAudioElement).duration)} />
    </div>
  );
}

export function VoiceoversGenerationPanel({
  session, workApplied, busy, run,
  preset, setPreset, previewText, setPreviewText,
  maxChars, setMaxChars, maxSeg, setMaxSeg,
  voiceStepState, refreshSession,
}: {
  session: Session | null; workApplied: string; busy: string | null; run: RunFn;
  preset: string; setPreset: (v: string) => void;
  previewText: string; setPreviewText: (v: string) => void;
  maxChars: number; setMaxChars: (v: number) => void;
  maxSeg: number; setMaxSeg: (v: number) => void;
  voiceStepState?: string; refreshSession?: () => void | Promise<void>;
}) {
  const isRunning = voiceStepState === "running";
  const isDone = voiceStepState === "done";
  const hasNarration = session?.has_narration ?? false;
  const narrationVersions = session?.narration_versions ?? [];
  const activeNarration = session?.active_narration ?? null;
  const narrationUrl = session?.urls?.narration ?? "";

  const prevStepState = useRef(voiceStepState);
  useEffect(() => {
    const prev = prevStepState.current;
    prevStepState.current = voiceStepState;
    if (prev === "running" && voiceStepState === "done" && refreshSession) void refreshSession();
  }, [voiceStepState, refreshSession]);

  useEffect(() => {
    if (!preset && session?.voice_presets?.includes("xtts_v2_es")) setPreset("xtts_v2_es");
  }, [preset, session?.voice_presets, setPreset]);

  const handleSelect = async (name: string) => {
    await postJson("/api/narration/select", { work: workApplied, name });
    if (refreshSession) await refreshSession();
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`¿Eliminar la narración "${name}"?`)) return;
    await fetch(`/api/narration?work=${encodeURIComponent(workApplied)}&name=${encodeURIComponent(name)}`, { method: "DELETE" });
    if (refreshSession) await refreshSession();
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">

      {/* Info */}
      <div className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs text-slate-400">
        <span className="font-semibold text-white">Voiceovers Generation</span> sintetiza la
        narración completa del guion usando <strong className="text-slate-300">Coqui XTTS v2</strong> con clonación de voz.
        El resultado se guarda como <code className="rounded bg-slate-700 px-1">narracion.wav</code> y
        sincroniza con las imágenes en el paso de render. Puedes generar varias versiones y elegir la mejor.
      </div>

      {isRunning && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Generando narración con XTTS… (guion de 20 min puede tardar 15–40 min en CPU)
        </div>
      )}

      {/* Active narration */}
      {hasNarration && narrationUrl && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold tracking-wider capitalize text-white">Narración Activa</div>
            <div className="flex items-center gap-2">
              {isDone && <span className="rounded-full bg-emerald-700/50 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">✓ Completado</span>}
              <button className="rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-700"
                onClick={() => refreshSession && void refreshSession()}>↺ Recargar</button>
            </div>
          </div>
          <NarrationPlayer key={narrationUrl} url={narrationUrl} label={activeNarration ?? "narracion.wav"} active />
        </div>
      )}

      {/* Versions */}
      {narrationVersions.length > 1 && (
        <Section id="voice-versions" title={`Versiones Guardadas (${narrationVersions.length})`} description="Historial de versiones de narración generadas para esta sesión.">
          <div className="space-y-2">
            {narrationVersions.map((v) => (
              <NarrationPlayer key={v.name} url={v.url} label={v.name} active={v.active}
                onSelect={v.active ? undefined : () => void handleSelect(v.name)}
                onDelete={() => void handleDelete(v.name)} />
            ))}
          </div>
        </Section>
      )}

      {/* Process info */}
      <Section id="voice-process" title="Proceso De Generación" description="Detalles técnicos del motor XTTS v2 y parámetros de la síntesis.">
        <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-slate-400">
          <li>Motor: <strong className="text-slate-300">Coqui XTTS v2</strong> — clonación de voz en español con ~15–60 s de muestra</li>
          <li>Preset activo: <code className="rounded bg-slate-700 px-1">{preset || "xtts_v2_es"}</code></li>
          <li>Guion fragmentado en bloques de <strong className="text-slate-300">{maxChars} caracteres</strong></li>
          <li>Fragmentos a generar: <strong className="text-slate-300">{maxSeg === 0 ? "todos" : maxSeg}</strong></li>
          <li>Salida: <code className="rounded bg-slate-700 px-1">narracion.wav</code> (PCM 22 kHz mono)</li>
          <li>Tiempo estimado: ~1 min/min de audio en GPU · 3–5× más en CPU</li>
        </ul>
      </Section>

      {/* Voice clone */}
      <Section id="voice-clone" title="Muestra De Voz Para Clonación" description="Sube 15–60 s de tu voz limpia para que XTTS clone el timbre.">
        <div className="space-y-3">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-300">
            Graba 15–60 s de tu voz sin música ni reverberación. Cuanto más limpia, mejor la clonación.
          </div>
          <div>
            <Label>Subir muestra (MP3, WAV, M4A…)</Label>
            <input type="file" accept="audio/*,.mp3,.wav,.m4a"
              className="mt-1 block w-full text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-slate-200 hover:file:bg-slate-600"
              onChange={async (e) => {
                const f = e.target.files?.[0]; e.target.value = "";
                if (!f) return;
                await run("subir clon", async () => {
                  const fd = new FormData(); fd.append("work", workApplied); fd.append("file", f);
                  const r = await fetch("/api/upload-voice-clone", { method: "POST", body: fd });
                  if (!r.ok) throw new Error(await r.text());
                  if (refreshSession) await refreshSession();
                });
              }} />
          </div>
          {session?.has_clone_reference && (
            <div className="space-y-2">
              <Label>Muestra activa</Label>
              <div className="flex items-center gap-2 rounded-xl border border-slate-600 bg-slate-700 p-2">
                <audio className="flex-1" controls src={session.urls?.clone_reference ?? ""} />
                <Btn className="shrink-0 border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600 text-xs" disabled={!!busy}
                  onClick={() => run("quitar clon", async () => {
                    await postJson("/api/clear-voice-clone", { work: workApplied });
                    if (refreshSession) await refreshSession();
                  })}>
                  Quitar
                </Btn>
              </div>
            </div>
          )}
        </div>
      </Section>

      {/* Config & generate */}
      <Section id="voice-config" title="Configuración Y Generación" description="Preset de voz, tamaño de fragmentos y texto de prueba.">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>Preset de voz</Label>
              <Select value={preset} onChange={(e) => setPreset(e.target.value)}>
                {(session?.voice_presets ?? []).map((p) => (<option key={p} value={p}>{p}</option>))}
              </Select>
            </div>
            <div>
              <Label>Máx. chars/fragmento</Label>
              <Input type="number" value={maxChars} onChange={(e) => setMaxChars(Number(e.target.value))} />
            </div>
            <div>
              <Label>Máx. fragmentos (0 = todos)</Label>
              <Input type="number" value={maxSeg} onChange={(e) => setMaxSeg(Number(e.target.value))} />
            </div>
            <div className="flex flex-col justify-end">
              <Label>Texto de prueba (preview)</Label>
              <Input value={previewText} onChange={(e) => setPreviewText(e.target.value)} placeholder="Escribe una frase para probar la voz…" />
            </div>
          </div>

          {(session?.voice_previews ?? []).length > 0 && (
            <div className="space-y-1">
              <Label>Muestras de preview generadas</Label>
              {(session?.voice_previews ?? []).map((pv) => (
                <div key={pv.name} className="flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-700 p-2">
                  <audio className="flex-1 h-8" controls src={pv.url} />
                  <span className="text-[10px] text-slate-400 truncate max-w-24">{pv.name}</span>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-2 border-t border-slate-600 pt-3">
            <Btn className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600" disabled={!!busy || isRunning}
              onClick={() => run("voice preview", async () => {
                await postJson("/api/voice-preview", { work: workApplied, preset, text: previewText });
                if (refreshSession) await refreshSession();
              })}>
              Generar preview de voz
            </Btn>
            <Btn className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40" disabled={!!busy || !session?.has_script || isRunning}
              onClick={() => run("narración completa", async () => {
                await postJson("/api/speak-script", { work: workApplied, preset, max_chars: maxChars, max_segments: maxSeg });
                if (refreshSession) await refreshSession();
              })}>
              {isRunning ? "Generando…" : hasNarration ? "Regenerar narracion.wav" : "Generar narracion.wav"}
            </Btn>
          </div>
        </div>
      </Section>
    </div>
  );
}
