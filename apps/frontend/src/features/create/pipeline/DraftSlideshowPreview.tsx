import { useCallback, useEffect, useRef, useState } from "react";
import { Btn } from "../../../components/ui";

export type PreviewSegment = {
  order: number;
  chunk_id: string;
  filename: string;
  image_url: string;
  audio_url: string | null;
  duration_ms: number;
  narration_text: string;
  scene_description_es?: string;
  has_audio: boolean;
};

type PreviewTimeline = {
  ok: boolean;
  error?: string;
  segment_count?: number;
  chunk_gap_ms?: number;
  total_duration_ms?: number;
  segments: PreviewSegment[];
};

function formatMs(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}:${String(r).padStart(2, "0")}` : `${r}s`;
}

export function DraftSlideshowPreview({ workApplied }: { workApplied: string }) {
  const [timeline, setTimeline] = useState<PreviewTimeline | null>(null);
  const [loading, setLoading] = useState(false);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rangeFrom, setRangeFrom] = useState(1);
  const [rangeTo, setRangeTo] = useState(12);
  const audioRef = useRef<HTMLAudioElement>(null);
  const gapTimerRef = useRef<number | null>(null);

  const loadTimeline = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(
        `/api/pipeline/render-preview/timeline?work=${encodeURIComponent(workApplied)}`,
      );
      const j = (await r.json()) as PreviewTimeline;
      setTimeline(j);
      if (j.ok && j.segments.length > 0) {
        setIndex(0);
        setRangeFrom(1);
        setRangeTo(Math.min(12, j.segments.length));
      }
    } catch {
      setTimeline({ ok: false, error: "No se pudo cargar el timeline.", segments: [] });
    } finally {
      setLoading(false);
    }
  }, [workApplied]);

  useEffect(() => {
    void loadTimeline();
  }, [loadTimeline]);

  const segments = timeline?.ok ? timeline.segments : [];
  const gapMs = timeline?.chunk_gap_ms ?? 0;
  const seg = segments[index];
  const clearGapTimer = () => {
    if (gapTimerRef.current != null) {
      window.clearTimeout(gapTimerRef.current);
      gapTimerRef.current = null;
    }
  };

  const advance = useCallback(() => {
    setIndex((prev) => {
      let next = prev + 1;
      while (next < segments.length && segments[next].order < rangeFrom) {
        next += 1;
      }
      if (next >= segments.length || segments[next].order > rangeTo) {
        setPlaying(false);
        return prev;
      }
      return next;
    });
  }, [segments, rangeFrom, rangeTo]);

  const playSegment = useCallback(
    (i: number) => {
      const s = segments[i];
      if (!s) return;
      const el = audioRef.current;
      if (!s.audio_url || !el) {
        gapTimerRef.current = window.setTimeout(() => advance(), Math.max(s.duration_ms, 500));
        return;
      }
      el.src = s.audio_url;
      el.currentTime = 0;
      void el.play().catch(() => {
        gapTimerRef.current = window.setTimeout(() => advance(), s.duration_ms);
      });
    },
    [segments, advance],
  );

  useEffect(() => {
    if (!playing || !seg) return;
    playSegment(index);
  }, [playing, index, seg?.order, playSegment]);

  useEffect(() => () => clearGapTimer(), []);

  const onAudioEnded = () => {
    if (!playing) return;
    clearGapTimer();
    const pauseMs = index < segments.length - 1 ? gapMs : 0;
    gapTimerRef.current = window.setTimeout(() => advance(), pauseMs);
  };

  const startPlayback = (fromOrder: number) => {
    const i = segments.findIndex((s) => s.order >= fromOrder);
    if (i < 0) return;
    clearGapTimer();
    setIndex(i);
    setPlaying(true);
  };

  const stopPlayback = () => {
    clearGapTimer();
    setPlaying(false);
    audioRef.current?.pause();
  };

  if (loading) {
    return <p className="text-xs text-slate-500">Cargando preview del montaje…</p>;
  }

  if (!timeline?.ok) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
        {timeline?.error ?? "No hay timeline de preview."}
        <Btn type="button" className="ml-2 text-xs" onClick={() => void loadTimeline()}>
          Reintentar
        </Btn>
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-sky-200 bg-sky-50/50 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-sky-950">Preview instantáneo (sin esperar al render)</p>
          <p className="text-[11px] text-sky-800/90 mt-0.5">
            Reproduce imagen + locución por bloque, con la misma sincronía que el draft (
            {timeline.segment_count} planos · ~{formatMs(timeline.total_duration_ms ?? 0)} total).
          </p>
        </div>
        <Btn
          type="button"
          className="bg-white text-sky-900 ring-1 ring-sky-200 text-xs"
          onClick={() => void loadTimeline()}
        >
          Recargar
        </Btn>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[11px] text-sky-900">
        <span>Rango preview</span>
        <input
          type="number"
          min={1}
          max={segments.length}
          value={rangeFrom}
          onChange={(e) => setRangeFrom(Math.max(1, parseInt(e.target.value, 10) || 1))}
          className="w-14 rounded border border-sky-200 px-1.5 py-0.5"
        />
        <span>–</span>
        <input
          type="number"
          min={1}
          max={segments.length}
          value={rangeTo}
          onChange={(e) => setRangeTo(Math.min(segments.length, Math.max(1, parseInt(e.target.value, 10) || 1)))}
          className="w-14 rounded border border-sky-200 px-1.5 py-0.5"
        />
        <span className="text-sky-700">bloques</span>
      </div>

      {seg ? (
        <div className="overflow-hidden rounded-xl border border-sky-100 bg-black">
          <img
            src={seg.image_url}
            alt={seg.scene_description_es || `Plano ${seg.order}`}
            className="aspect-video w-full object-contain"
          />
        </div>
      ) : null}

      <audio ref={audioRef} className="w-full" onEnded={onAudioEnded} preload="auto" />

      <div className="flex flex-wrap items-center gap-2">
        {!playing ? (
          <Btn
            type="button"
            className="bg-sky-600 text-white hover:bg-sky-500 text-xs"
            onClick={() => startPlayback(rangeFrom)}
          >
            ▶ Reproducir rango
          </Btn>
        ) : (
          <Btn type="button" className="bg-slate-700 text-white text-xs" onClick={stopPlayback}>
            ⏸ Pausar
          </Btn>
        )}
        <Btn
          type="button"
          className="bg-white text-sky-900 ring-1 ring-sky-200 text-xs"
          disabled={index <= 0}
          onClick={() => {
            stopPlayback();
            setIndex(Math.max(0, index - 1));
          }}
        >
          ← Anterior
        </Btn>
        <Btn
          type="button"
          className="bg-white text-sky-900 ring-1 ring-sky-200 text-xs"
          disabled={index >= segments.length - 1}
          onClick={() => {
            stopPlayback();
            setIndex(Math.min(segments.length - 1, index + 1));
          }}
        >
          Siguiente →
        </Btn>
        <span className="text-[11px] text-sky-800">
          Bloque <strong>{seg?.order ?? "—"}</strong> / {segments.length}
          {seg?.duration_ms ? ` · ${formatMs(seg.duration_ms)}` : ""}
          {!seg?.has_audio ? " · sin audio" : ""}
        </span>
      </div>

      {seg?.narration_text ? (
        <p className="text-xs text-slate-700 leading-relaxed border-t border-sky-100 pt-2">
          {seg.narration_text}
        </p>
      ) : null}
    </div>
  );
}
