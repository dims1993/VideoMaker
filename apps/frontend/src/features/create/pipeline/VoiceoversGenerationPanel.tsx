import { Btn, Input, Label, Select } from "../../../components/ui";
import { postJson } from "../../../services/api";
import type { Session } from "../../../types/session";
import type { RunFn } from "../types";

export function VoiceoversGenerationPanel({
  session,
  workApplied,
  busy,
  run,
  preset,
  setPreset,
  previewText,
  setPreviewText,
  maxChars,
  setMaxChars,
  maxSeg,
  setMaxSeg,
}: {
  session: Session | null;
  workApplied: string;
  busy: string | null;
  run: RunFn;
  preset: string;
  setPreset: (v: string) => void;
  previewText: string;
  setPreviewText: (v: string) => void;
  maxChars: number;
  setMaxChars: (v: number) => void;
  maxSeg: number;
  setMaxSeg: (v: number) => void;
}) {
  return (
    <div className="space-y-3">
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
          <li>Si suena raro, prueba otra muestra más limpia.</li>
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
            {(session?.voice_presets ?? []).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
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
              await postJson("/api/speak-script", { work: workApplied, preset, max_chars: maxChars, max_segments: maxSeg });
            })
          }
        >
          Generar narracion.wav
        </Btn>
      </div>
    </div>
  );
}
