import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Btn, ExpandableTextArea, Input, Label, Select, TextArea } from "../../../components/ui";
import {
  deleteReq,
  patchJson,
  postJson,
  putJson,
  readApiError,
} from "../../../services/api";
import type {
  ScriptWriterLibraryStore,
  ScriptWriterNarrativePreset,
} from "../scriptWriter/useScriptWriterLibrary";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

// ── AI Script Writer Generator ───────────────────────────────────────────
function AIScriptWriterGenerator({
  onGenerated,
}: {
  onGenerated: (t: Record<string, unknown>) => void;
}) {
  const [transcriptText, setTranscriptText] = useState("");
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => setTranscriptText((ev.target?.result as string) ?? "");
    reader.readAsText(file);
  };

  const handleGenerate = async () => {
    if (!transcriptText.trim()) { setError("Carga un documento o pega el contenido primero."); return; }
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/script-writer-templates/generate-from-transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript_text: transcriptText }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(j.detail ?? `Error ${res.status}`);
      }
      const data = await res.json() as Record<string, unknown>;
      onGenerated(data);
      setTranscriptText("");
      setFileName("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-600 bg-slate-800 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Generador De Template Con IA</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Carga las transcripciones del canal y Claude Sonnet analizará el estilo de guion y rellenará todos los campos del template automáticamente.
          </div>
        </div>
        <span className="shrink-0 rounded-md border border-violet-500/40 bg-violet-950/40 px-2 py-0.5 text-[10px] font-mono text-violet-300">
          Claude Sonnet
        </span>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Documento de transcripciones</label>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => fileRef.current?.click()}
            className="rounded-lg border border-slate-600 bg-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-600 transition-colors">
            Seleccionar archivo
          </button>
          {fileName ? (
            <>
              <span className="text-xs text-slate-400 truncate max-w-[180px]" title={fileName}>{fileName}</span>
              <button type="button" onClick={() => { setFileName(""); setTranscriptText(""); if (fileRef.current) fileRef.current.value = ""; }}
                className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
            </>
          ) : (
            <span className="text-xs text-slate-500">.json, .txt o .md</span>
          )}
          <input ref={fileRef} type="file" accept=".json,.txt,.md" className="hidden" onChange={handleFile} />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          O pega el contenido directamente
          {transcriptText && <span className="ml-2 text-slate-500">({transcriptText.length.toLocaleString()} chars)</span>}
        </label>
        <textarea
          value={transcriptText}
          onChange={(e) => { setTranscriptText(e.target.value); setFileName(""); }}
          placeholder="Pega aquí las transcripciones del canal…"
          rows={4}
          className="w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:border-slate-400 focus:outline-none resize-none"
        />
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-400">{error}</div>
      )}

      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-slate-500">Requiere <code className="rounded bg-slate-700 px-1">ANTHROPIC_API_KEY</code> en .env</span>
        <div className="flex items-center gap-2">
          {loading && <span className="text-xs text-violet-400 animate-pulse">Claude analizando…</span>}
          <Btn type="button" className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
            disabled={loading || !transcriptText.trim()} onClick={handleGenerate}>
            {loading ? "Analizando…" : "Analizar y rellenar template"}
          </Btn>
        </div>
      </div>
    </div>
  );
}

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

type SavedGuionEntry = {
  id: string;
  title: string;
  created_at: string;
  byte_len: number;
  preview: string;
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
  setModel: Dispatch<SetStateAction<string>>;
  scriptFragmentIndex: number | null;
  setScriptFragmentIndex: (v: number | null) => void;
  refreshPipeline: () => Promise<void>;
}) {
  const lib = library;
  const [scriptText, setScriptText] = useState("");
  const [scriptUnderlineMode, setScriptUnderlineMode] = useState(false);
  const [scriptAnnotatedHtml, setScriptAnnotatedHtml] = useState<string>("");
  const [scriptDirty, setScriptDirty] = useState(false);
  const [manualEditMode, setManualEditMode] = useState(false);
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
  const [savedGuiones, setSavedGuiones] = useState<SavedGuionEntry[]>([]);
  const [saveToLibTitle, setSaveToLibTitle] = useState("");
  const [selectedSavedId, setSelectedSavedId] = useState("");
  const fileImportRef = useRef<HTMLInputElement>(null);
  const [scriptEditorFullscreen, setScriptEditorFullscreen] = useState(false);
  const scriptModalTextareaRef = useRef<HTMLTextAreaElement>(null);
  const scriptUnderlineRef = useRef<HTMLDivElement>(null);
  const underlineHydratedRef = useRef(false);
  const scriptTextRef = useRef("");
  const scriptCaretOffsetRef = useRef<number | null>(null);

  const _getTextCaretOffset = useCallback((el: HTMLElement): number => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return 0;
    const range = sel.getRangeAt(0);
    // Ensure selection is inside this element
    if (!el.contains(range.startContainer)) return 0;
    const pre = document.createRange();
    pre.selectNodeContents(el);
    pre.setEnd(range.startContainer, range.startOffset);
    return pre.toString().length;
  }, []);

  const _setTextCaretOffset = useCallback((el: HTMLElement, offset: number) => {
    const textNodes: Text[] = [];
    const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n: Node | null;
    // eslint-disable-next-line no-cond-assign
    while ((n = walk.nextNode())) textNodes.push(n as Text);

    let remaining = Math.max(0, offset);
    let targetNode: Text | null = null;
    let targetOffset = 0;
    for (const t of textNodes) {
      const len = t.data.length;
      if (remaining <= len) {
        targetNode = t;
        targetOffset = remaining;
        break;
      }
      remaining -= len;
    }
    if (!targetNode) {
      // fallback end
      targetNode = textNodes[textNodes.length - 1] ?? null;
      targetOffset = targetNode ? targetNode.data.length : 0;
    }
    const sel = window.getSelection();
    if (!sel) return;
    const r = document.createRange();
    if (targetNode) r.setStart(targetNode, targetOffset);
    else r.setStart(el, 0);
    r.collapse(true);
    sel.removeAllRanges();
    sel.addRange(r);
  }, []);

  const _toggleUnderlineSelection = useCallback((rootEl: HTMLElement): boolean => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return false;
    const range = sel.getRangeAt(0);
    if (range.collapsed) return false;
    if (!rootEl.contains(range.commonAncestorContainer)) return false;

    // Use execCommand underline for true toggle behavior.
    // It's deprecated but still works across browsers for simple rich-text toggles.
    try {
      rootEl.focus();
      // eslint-disable-next-line deprecation/deprecation
      document.execCommand("underline");
      return true;
    } catch {
      return false;
    }
  }, []);

  const underlineStorageKey = useMemo(
    () => `videomaker:script_underlines:${workApplied}`,
    [workApplied],
  );

  const toSafeHtml = useCallback((t: string) => {
    // Minimal HTML escape for local-only annotated editor.
    return (t ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;")
      .replaceAll("\n", "<br/>");
  }, []);

  const loadUnderlinesFromStorage = useCallback(() => {
    try {
      const raw = localStorage.getItem(underlineStorageKey);
      if (raw && raw.trim()) return raw;
    } catch {
      /* ignore */
    }
    return "";
  }, [underlineStorageKey]);

  const saveUnderlinesToStorage = useCallback(
    (html: string) => {
      try {
        localStorage.setItem(underlineStorageKey, html);
      } catch {
        /* ignore */
      }
    },
    [underlineStorageKey],
  );

  useEffect(() => {
    scriptTextRef.current = scriptText;
  }, [scriptText]);

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

  const loadScript = useCallback(async (opts?: { force?: boolean }) => {
    // Don't overwrite while the user is editing (prevents cursor jumps).
    if (!opts?.force && (scriptEditorFullscreen || scriptDirty)) return;
    const r = await fetch(
      `/api/script?work=${encodeURIComponent(workApplied)}`,
    );
    if (!r.ok) return;
    const j = (await r.json()) as {
      text?: string;
      structured?: Record<string, unknown>;
    };
    setScriptText(j.text ?? "");
    setScriptDirty(false);
  }, [workApplied]);

  useEffect(() => {
    void loadScript();
  }, [loadScript, scriptStepState, workApplied]);

  // When a template is applied, restore session defaults from it.
  useEffect(() => {
    if (!lib.scriptWriterTemplateId) return;
    if (lib.swSessionKeywords.trim()) setKw(lib.swSessionKeywords);
    if (lib.swSessionContext.trim()) setCtx(lib.swSessionContext);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lib.scriptWriterTemplateId, lib.swSessionKeywords, lib.swSessionContext]);

  const loadSavedGuiones = useCallback(async () => {
    try {
      const r = await fetch("/api/saved-guiones?limit=100");
      if (!r.ok) return;
      const j = (await r.json()) as { items?: SavedGuionEntry[] };
      setSavedGuiones(Array.isArray(j.items) ? j.items : []);
    } catch {
      setSavedGuiones([]);
    }
  }, []);

  useEffect(() => {
    void loadSavedGuiones();
  }, [loadSavedGuiones]);

  useEffect(() => {
    if (!scriptEditorFullscreen) {
      underlineHydratedRef.current = false;
      return;
    }

    // Hydrate ONLY once per open. Never on keystrokes.
    if (!underlineHydratedRef.current) {
      underlineHydratedRef.current = true;
      const stored = loadUnderlinesFromStorage();
      const initial = stored || toSafeHtml(scriptTextRef.current);
      setScriptAnnotatedHtml(initial);
      if (scriptUnderlineRef.current) scriptUnderlineRef.current.innerHTML = initial;
    }

    const ta = scriptModalTextareaRef.current;
    if (ta && !scriptUnderlineMode) ta.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setScriptEditorFullscreen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scriptEditorFullscreen, loadUnderlinesFromStorage, scriptUnderlineMode, toSafeHtml]);

  useEffect(() => {
    if (!scriptEditorFullscreen) return;
    if (!scriptUnderlineMode) return;
    const el = scriptUnderlineRef.current;
    if (!el) return;
    el.focus();
  }, [scriptEditorFullscreen, scriptUnderlineMode]);

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

  /** Solo durante la inferencia del LLM: no guardar (condición de carrera). Con paso «done» sí puedes editar el texto. */
  const scriptIoLocked = scriptStepState === "running";
  const effectiveLocked = locked && !manualEditMode;
  const sessionSectionKey = useMemo(
    () => `videomaker:sw_session_enabled:${workApplied}`,
    [workApplied],
  );
  const [sessionEnabled, setSessionEnabled] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(sessionSectionKey);
      if (v === "0") return false;
      if (v === "1") return true;
    } catch {
      /* ignore */
    }
    return true;
  });

  const setSessionEnabledPersisted = useCallback(
    (v: boolean) => {
      setSessionEnabled(v);
      try {
        localStorage.setItem(sessionSectionKey, v ? "1" : "0");
      } catch {
        /* ignore */
      }
    },
    [sessionSectionKey],
  );

  const lockReason = scriptStepState === "running" ? "Generando guion con el LLM…" : null;
  return (
    <div className={`rounded-2xl bg-slate-900 p-4 space-y-3 ${locked ? "opacity-95" : ""}`}>

      {/* ── Avisos ── */}
      {lockReason && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          <span className="font-semibold">Generando.</span> {lockReason} Espera a que termine antes de guardar el guion.
          Para cambiar plantilla o regenerar desde cero usa <strong>Reset</strong> en la pipeline.
        </div>
      )}
      {locked && !scriptIoLocked && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          <span className="font-semibold">Bloqueado.</span> Paso Script Writer ya ejecutado. Puedes{" "}
          <strong>editar y guardar</strong> el texto del guion abajo; para regenerar usa{" "}
          <strong>Reset</strong> en la pipeline (arriba).
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Btn
              type="button"
              className="bg-white text-slate-900 hover:bg-slate-100"
              onClick={() => setManualEditMode(true)}
              disabled={manualEditMode}
            >
              Editar plantilla (desbloquear)
            </Btn>
            {manualEditMode && (
              <span className="text-[11px] text-amber-200">
                Modo edición activo: al guardar el guion se volverá a bloquear.
              </span>
            )}
          </div>
        </div>
      )}

      <fieldset disabled={effectiveLocked} className="min-w-0 space-y-3 border-0 p-0">

        {/* ── Template selector ── */}
        <div className="flex flex-wrap items-end justify-between gap-2 rounded-xl border border-slate-600 bg-gradient-to-r from-slate-800 to-slate-700 px-4 py-3 shadow-md">
          <div className="min-w-[260px] flex-1">
            <label className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Template Script Writer
            </label>
            <select
              value={lib.scriptWriterTemplateId}
              onChange={async (e) => {
                const id = e.target.value;
                lib.setScriptWriterTemplateId(id);
                if (!id) return;
                await lib.applyTemplateFromApi(id);
              }}
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-200 focus:border-slate-400 focus:outline-none"
            >
              <option value="">(nuevo template)</option>
              {lib.scriptWriterTemplates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
              onClick={() => run("Recargar templates SW", async () => { await lib.loadScriptWriterTemplates(); })}>
              Reload
            </Btn>
            <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100" disabled={!lib.swName.trim()}
              onClick={() => run("Guardar template Script Writer", async () => { await lib.saveTemplate(); })}>
              Save
            </Btn>
            <Btn type="button" className="border border-rose-500/50 bg-rose-950/40 text-rose-400 hover:bg-rose-950/70 disabled:opacity-40"
              disabled={!lib.scriptWriterTemplateId}
              onClick={() => run("Eliminar template Script Writer", async () => {
                if (!lib.scriptWriterTemplateId) return;
                if (!confirm("¿Eliminar este template de Script Writer?")) return;
                await lib.deleteTemplate();
              })}>
              Delete
            </Btn>
          </div>
        </div>

        {/* ── Generador IA: solo en modo nuevo template ── */}
        {!lib.scriptWriterTemplateId && !effectiveLocked && (
          <AIScriptWriterGenerator
            onGenerated={(data) => {
              lib.applyTemplateFields(data as Parameters<typeof lib.applyTemplateFields>[0]);
            }}
          />
        )}

        {/* ── Template settings ── */}
        <Section id="sw-template" title="Configuración Del Template" description="Nombre, ritmo, densidad narrativa y estructura de actos del guion.">
          <div className="space-y-3">
            <div>
              <Label>Nombre</Label>
              <Input value={lib.swName} onChange={(e) => lib.setSwName(e.target.value)} placeholder="Ej: Long-form finanzas · ritmo documental" />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <Label>Ritmo (VO)</Label>
                <Select value={lib.swPacing} onChange={(e) => lib.setSwPacing(e.target.value as typeof lib.swPacing)}>
                  <option value="">(sin override: hereda de Prompt)</option>
                  <option value="short">Corto / rápido</option>
                  <option value="mixed">Mixto</option>
                  <option value="long">Largo / documental</option>
                </Select>
              </div>
              <div>
                <Label>Densidad de datos</Label>
                <Select value={lib.swDataDensity} onChange={(e) => lib.setSwDataDensity(e.target.value as typeof lib.swDataDensity)}>
                  <option value="">(por defecto)</option>
                  <option value="low">Baja (historia / metáfora)</option>
                  <option value="medium">Media</option>
                  <option value="high">Alta (cifras, series temporales)</option>
                </Select>
              </div>
              <div>
                <Label>Estructura de escenas</Label>
                <Select value={lib.swStructure} onChange={(e) => {
                  const v = e.target.value as typeof lib.swStructure;
                  lib.setSwStructure(v);
                  if (v !== "four_act") lib.setSwNarrativePreset("");
                }}>
                  <option value="">(por defecto: 5 bloques)</option>
                  <option value="default_five_blocks">5 bloques (intro + 3 pilares + cierre)</option>
                  <option value="four_act">4 actos (hook → promesa → cuerpo → cierre)</option>
                </Select>
              </div>
            </div>

            {lib.swStructure === "four_act" && (
              <div className="rounded-xl border border-slate-600 bg-slate-700/50 px-3 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">Reparto orientativo (4 actos)</div>
                <div className="mt-3 grid gap-3 lg:grid-cols-3">
                  <div>
                    <Label>Categoría narrativa</Label>
                    <Select value={lib.swNarrativePreset} onChange={(e) => {
                      const v = e.target.value as ScriptWriterNarrativePreset;
                      if (v === "") { lib.setSwNarrativePreset(""); lib.setSwFragmentWeights(""); return; }
                      if (v === "custom") { lib.setSwNarrativePreset("custom"); return; }
                      const p = narrativePresets.find((x) => x.id === v);
                      lib.setSwNarrativePreset(v);
                      if (p?.weights?.length === 4) lib.setSwFragmentWeights(p.weights.join(", "));
                    }}>
                      <option value="">Seleccione categoría</option>
                      {narrativePresets.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                      <option value="custom">Personalizado (editar pesos en fragmentación)</option>
                    </Select>
                  </div>
                  <div className="lg:col-span-2 overflow-x-auto">
                    {fourActPreview && fourActPreview.length === 4 && (
                      <table className="w-full min-w-[340px] border-collapse text-left text-[11px]">
                        <thead>
                          <tr className="border-b border-slate-600 text-slate-400">
                            <th className="py-1 pr-2 font-medium">Acto</th>
                            <th className="py-1 pr-2 font-medium">Segmento</th>
                            <th className="py-1 pr-2 font-medium">Peso</th>
                            <th className="py-1 pr-2 font-medium">Min</th>
                            <th className="py-1 font-medium">Palabras</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fourActPreview.map((row, i) => (
                            <tr key={i} className="border-b border-slate-700 text-slate-300">
                              <td className="py-1 pr-2 font-mono text-slate-400">{["I", "II", "III", "IV"][i]}</td>
                              <td className="py-1 pr-2">{row.label}</td>
                              <td className="py-1 pr-2 font-mono">{row.pct.toFixed(0)}%</td>
                              <td className="py-1 pr-2 font-mono">{row.min.toFixed(1)}</td>
                              <td className="py-1 font-mono">~{row.words}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    <p className="mt-2 text-[10px] text-slate-500">Duración del pipeline: {Number.isFinite(minutes) && minutes > 0 ? minutes : 20} min.</p>
                  </div>
                </div>
              </div>
            )}

            <div>
              <Label>Instrucciones sistema (overlay)</Label>
              <ExpandableTextArea
                value={lib.swSystem}
                onChange={lib.setSwSystem}
                placeholder="Reglas extra para la generación del guion (se añaden al system del LLM tras el template de Prompt)."
                modalTitle="Script Writer · Instrucciones sistema (overlay)"
                variant="output"
              />
            </div>
            <div>
              <Label>Instrucciones usuario (overlay)</Label>
              <ExpandableTextArea
                value={lib.swUser}
                onChange={lib.setSwUser}
                placeholder="Preferencias de formato, ejemplos a evitar, compliance…"
                modalTitle="Script Writer · Instrucciones usuario (overlay)"
                variant="output"
              />
            </div>

            {/* ── Inputs de sesión (para generación) ── */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label>Keywords (coma)</Label>
                <Input
                  value={kw}
                  onChange={(e) => {
                    const v = e.target.value;
                    setKw(v);
                    lib.setSwSessionKeywords(v);
                  }}
                  placeholder="tema, ángulo, intención…"
                />
              </div>
              <div className="sm:col-span-2">
                <ExpandableTextArea
                  label="Contexto"
                  value={ctx}
                  onChange={(v) => {
                    setCtx(v);
                    lib.setSwSessionContext(v);
                  }}
                  placeholder="Público, tono, datos que deben aparecer…"
                  modalTitle="Contexto del Script Writer"
                  variant="output"
                />
              </div>
            </div>
          </div>
        </Section>

        {/* ── Sesión + Fragmentación (switch) ── */}
        <div className={`overflow-hidden rounded-xl border transition-all ${sessionEnabled ? "border-slate-700 shadow-md" : "border-slate-600 hover:border-slate-500"}`}>
          <div className="flex w-full items-start justify-between gap-3 bg-gradient-to-r from-slate-800 to-slate-700 px-4 py-3 text-left">
            <div className="flex min-w-0 flex-1 flex-col gap-y-0.5">
              <div className="flex items-center gap-2">
                <span className="shrink-0 text-sm font-semibold tracking-wider capitalize text-white">
                  Sesión de ejecución y fragmentación
                </span>
                <span className="shrink-0 rounded bg-slate-600 px-1.5 py-0.5 text-[10px] text-slate-300 font-mono">
                  opcional
                </span>
              </div>
              <span className="text-[11px] leading-snug text-slate-400 font-normal">
                Overrides para esta ejecución (idioma, minutos, proveedor/modelo) y cómo se divide el guion en fragmentos.
              </span>
            </div>

            {/* iOS-like switch */}
            <button
              type="button"
              className="shrink-0"
              disabled={effectiveLocked}
              onClick={() => setSessionEnabledPersisted(!sessionEnabled)}
              aria-pressed={sessionEnabled}
              aria-label={sessionEnabled ? "Desactivar sección" : "Activar sección"}
            >
              <span
                className={[
                  "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
                  effectiveLocked ? "opacity-50" : "",
                  sessionEnabled ? "bg-emerald-500" : "bg-slate-500/70",
                ].join(" ")}
              >
                <span
                  className={[
                    "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
                    sessionEnabled ? "translate-x-5" : "translate-x-1",
                  ].join(" ")}
                />
              </span>
            </button>
          </div>

          {sessionEnabled && (
            <div className={[
              "border-t border-slate-700 bg-slate-800 px-4 pb-4 pt-3 space-y-4",
              "[&_label]:text-slate-400",
              "[&_input]:mt-1 [&_input]:bg-slate-700 [&_input]:border-slate-600 [&_input]:text-slate-200 [&_input]:placeholder:text-slate-500",
              "[&_input:focus]:bg-slate-700 [&_input:focus]:text-slate-100 [&_input:focus]:border-slate-400 [&_input:focus]:ring-slate-500/30",
              "[&_select]:mt-1 [&_select]:bg-slate-700 [&_select]:border-slate-600 [&_select]:text-slate-200",
              "[&_select:focus]:bg-slate-700 [&_select:focus]:text-slate-100 [&_select:focus]:border-slate-400",
              "[&_textarea]:bg-slate-700 [&_textarea]:border-slate-600 [&_textarea]:text-slate-200 [&_textarea]:placeholder:text-slate-500",
              "[&_textarea:focus]:bg-slate-700 [&_textarea:focus]:text-slate-100 [&_textarea:focus]:border-slate-400",
            ].join(" ")}>
              {/* Ejecución */}
              <div className="grid gap-3 sm:grid-cols-2">
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
                </div>
                <div>
                  <Label>Proveedor LLM</Label>
                  <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
                    <option value="">(usar .env)</option>
                    <option value="ollama">ollama</option>
                    <option value="openai">openai-compatible</option>
                  </Select>
                </div>
                <div>
                  <Label>Modelo</Label>
                  {useOpenAiModelField ? (
                    <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder={llmDefaults?.openai_model?.trim() || "gpt-4o-mini"} />
                  ) : (
                    <>
                      <Select value={model} onChange={(e) => setModel(e.target.value)}>
                        <option value="">Predeterminado (.env)</option>
                        {ollamaSelectOptions.map((name) => (<option key={name} value={name}>{name}</option>))}
                      </Select>
                      {ollamaListHint && <p className="mt-1 text-[11px] text-amber-400">{ollamaListHint}</p>}
                    </>
                  )}
                </div>
              </div>

              {/* Fragmentación */}
              <div className="space-y-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">
                  Fragmentación
                </div>
                <div className="max-w-xl">
                  <Label>Modo de fragmentación</Label>
                  <Select value={lib.swChunking} onChange={(e) => lib.setSwChunking(e.target.value as typeof lib.swChunking)}>
                    <option value="">Seleccione el modo</option>
                    <option value="full_pass">Guion completo en una pasada</option>
                    <option value="outline_act1_only">Solo OUTLINE + primer bloque</option>
                    <option value="sequential_fragments">{structureSequentialCopy.optionLabel}</option>
                  </Select>
                  {lib.swChunking === "sequential_fragments" && <p className="mt-1 text-[11px] text-slate-400">{structureSequentialCopy.helperSequential}</p>}
                </div>

                {lib.swChunking === "sequential_fragments" && (
                  <div className="rounded-xl border border-slate-600 bg-slate-700/40 px-3 py-3 space-y-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">Progreso por fragmentos</div>
                    <p className="text-[11px] text-slate-400">{structureSequentialCopy.weightsIntro}</p>
                    <div>
                      <Label>Pesos de minutos por fragmento (opcional)</Label>
                      <TextArea value={lib.swFragmentWeights} onChange={(e) => { lib.setSwFragmentWeights(e.target.value); if (lib.swStructure === "four_act") lib.setSwNarrativePreset("custom"); }}
                        className="min-h-[52px] font-mono text-[11px]"
                        placeholder={lib.swStructure === "four_act" ? "Ej: 0.14, 0.18, 0.46, 0.22" : "Ej: 0.10, 0.20, 0.22, 0.22, 0.26"}
                        disabled={effectiveLocked} />
                    </div>
                    <div className="flex flex-wrap items-end gap-2">
                      <div className="min-w-[220px] flex-1">
                        <Label>Qué fragmento genera "Start step"</Label>
                        <Select value={scriptFragmentIndex === null ? "" : String(scriptFragmentIndex)} onChange={(e) => { const v = e.target.value; setScriptFragmentIndex(v === "" ? null : Number(v)); }}>
                          <option value="">Automático (primer pendiente)</option>
                          {Array.from({ length: fragSteps.length > 0 ? fragSteps.length : lib.swStructure === "four_act" ? 4 : 5 }, (_, i) => (
                            <option key={i} value={String(i)}>Fragmento {i}{fragSteps[i]?.label ? ` · ${fragSteps[i].label}` : ""}</option>
                          ))}
                        </Select>
                      </div>
                      <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600" onClick={() => void loadFragState()}>Refrescar</Btn>
                      <Btn type="button" className="border border-rose-500/50 bg-rose-950/40 text-rose-400 hover:bg-rose-950/70"
                        onClick={() => run("Reiniciar fragmentación", async () => {
                          if (!confirm("¿Borrar estado y chunks guardados?")) return;
                          await postJson(`/api/script-fragmentation/reset`, { work: workApplied });
                          setScriptFragmentIndex(null);
                          await loadFragState();
                          await refreshPipeline();
                        })}>
                        Reiniciar
                      </Btn>
                    </div>
                    {!fragExists ? (
                      <p className="text-[11px] text-slate-500">Sin estado en disco aún. Aparecerá tras el primer Start step.</p>
                    ) : (
                      <ul className="space-y-2 border-t border-slate-600 pt-3">
                        {fragSteps.map((s, i) => (
                          <li key={`${s.id}-${i}`} className="flex flex-wrap items-center gap-2">
                            <span className="w-6 font-mono text-[11px] text-slate-400">{i}</span>
                            <span className="min-w-[120px] flex-1 text-slate-200 font-medium">{s.label}</span>
                            <span className="rounded-full border border-slate-600 bg-slate-700 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">{s.status}</span>
                            <label className="flex cursor-pointer items-center gap-1 text-[11px] text-slate-300">
                              <input type="checkbox" className="rounded border-slate-500" checked={s.status === "done"} disabled={effectiveLocked}
                                onChange={(e) => run(s.status === "done" ? "Marcar pendiente" : "Marcar completado", async () => {
                                  await patchJson(`/api/script-fragmentation`, { work: workApplied, index: i, complete: e.target.checked });
                                  await loadFragState();
                                  await refreshPipeline();
                                })} />
                              Completado
                            </label>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Biblioteca de guiones ── */}
        <Section id="sw-library" title="Biblioteca De Guiones" description="Archiva, importa o aplica copias de guiones guardadas en disco.">
          <div className="space-y-3">
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[12rem] flex-1">
                <Label>Título al archivar (opcional)</Label>
                <Input value={saveToLibTitle} onChange={(e) => setSaveToLibTitle(e.target.value)} placeholder="p. ej. Motivación v2" />
              </div>
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
                onClick={() => run("Archivar guion de sesión", async () => {
                  await postJson("/api/saved-guiones", { work: workApplied, title: saveToLibTitle.trim() || null });
                  await loadSavedGuiones();
                })}>
                Archivar sesión
              </Btn>
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
                onClick={() => run("Archivar texto del editor", async () => {
                  await postJson("/api/saved-guiones/raw", { text: scriptText, title: saveToLibTitle.trim() || null });
                  await loadSavedGuiones();
                })}>
                Archivar editor
              </Btn>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input ref={fileImportRef} type="file" accept=".txt,.md,text/plain,text/markdown" className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]; e.target.value = "";
                  if (!f) return;
                  void run("Subir guion a biblioteca", async () => {
                    const fd = new FormData();
                    fd.append("file", f); fd.append("title", saveToLibTitle.trim());
                    const r = await fetch("/api/saved-guiones/upload", { method: "POST", body: fd });
                    if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
                    await loadSavedGuiones();
                  });
                }} />
              <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100" onClick={() => fileImportRef.current?.click()}>
                Subir archivo
              </Btn>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[14rem] flex-1">
                <Label>Seleccionar copia guardada</Label>
                <Select value={selectedSavedId} onChange={(e) => setSelectedSavedId(e.target.value)}>
                  <option value="">— Elegir —</option>
                  {savedGuiones.map((s) => (<option key={s.id} value={s.id}>{s.title} · {(s.byte_len / 1024).toFixed(1)} KiB</option>))}
                </Select>
              </div>
              <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40" disabled={!selectedSavedId}
                onClick={() => run("Usar guion de biblioteca", async () => {
                  await postJson(`/api/saved-guiones/${encodeURIComponent(selectedSavedId)}/apply`, { work: workApplied });
                  await loadScript({ force: true }); await refreshPipeline();
                })}>
                Usar en sesión
              </Btn>
              <Btn type="button" className="border border-rose-500/50 bg-rose-950/40 text-rose-400 hover:bg-rose-950/70 disabled:opacity-40" disabled={!selectedSavedId}
                onClick={() => run("Eliminar copia", async () => {
                  await deleteReq(`/api/saved-guiones/${encodeURIComponent(selectedSavedId)}`);
                  setSelectedSavedId(""); await loadSavedGuiones();
                })}>
                Borrar copia
              </Btn>
            </div>
            <div className="flex flex-wrap gap-2 border-t border-slate-600 pt-2">
              <Btn type="button" className="bg-emerald-600 text-white hover:bg-emerald-700"
                onClick={() => run("Aplicar editor a sesión", async () => {
                  await postJson("/api/saved-guiones/apply-text", { work: workApplied, text: scriptText });
                  await loadScript({ force: true }); await refreshPipeline();
                })}>
                Aplicar texto del editor a la sesión
              </Btn>
            </div>
          </div>
        </Section>

      </fieldset>

      {/* ── Guion ── */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Salida · Guion</div>
          <div className="flex gap-2">
            <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadScript()}>
              Recargar desde disco
            </Btn>
          </div>
        </div>
        <div role="button" tabIndex={0} aria-label="Abrir editor de guion a pantalla completa"
          onClick={() => setScriptEditorFullscreen(true)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setScriptEditorFullscreen(true); } }}
          className={`min-h-[200px] w-full cursor-pointer rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-left font-mono text-xs leading-relaxed shadow-inner outline-none transition hover:border-slate-500 ${scriptText.trim() ? "text-slate-200" : "text-slate-500"}`}>
          <span className="block max-h-[280px] overflow-y-auto whitespace-pre-wrap">
            {scriptText.trim() ? scriptText : "Tras Start step aparecerá el guion aquí. Pulsa para abrir el editor completo."}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Btn className="bg-white text-slate-900 hover:bg-slate-100" disabled={scriptIoLocked}
            onClick={() => run("Guardar guion", async () => {
              await putJson(`/api/script`, { work: workApplied, text: scriptText });
              await loadScript({ force: true });
              setManualEditMode(false);
            })}>
            Guardar en sesión
          </Btn>
          <span className="self-center text-[11px] text-slate-500">
            Guarda en <code className="rounded bg-slate-700 px-1">guion.txt</code> y sincroniza <code className="rounded bg-slate-700 px-1">pipeline/script.json</code>.
          </span>
        </div>
      </div>

      {scriptEditorFullscreen && (
        <div className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4"
          role="dialog" aria-modal="true" aria-label="Editor de guion a pantalla completa">
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">Editor de guion · vista completa</span>
              <div className="flex flex-wrap items-center gap-2">
                <label className="mr-1 inline-flex cursor-pointer items-center gap-2 text-[11px] text-slate-600">
                  <input
                    type="checkbox"
                    className="rounded border-slate-300"
                    checked={scriptUnderlineMode}
                    disabled={scriptIoLocked}
                  onChange={(e) => {
                      const next = e.target.checked;
                      // store current caret from whichever editor is active
                      if (scriptUnderlineMode && scriptUnderlineRef.current) {
                        scriptCaretOffsetRef.current = _getTextCaretOffset(scriptUnderlineRef.current);
                      } else if (scriptModalTextareaRef.current) {
                        scriptCaretOffsetRef.current = scriptModalTextareaRef.current.selectionStart ?? null;
                      }

                      setScriptUnderlineMode(next);
                      // Ensure annotated HTML exists when enabling.
                      if (next && !scriptAnnotatedHtml.trim()) {
                        const stored = loadUnderlinesFromStorage();
                        setScriptAnnotatedHtml(stored || toSafeHtml(scriptText));
                      }
                      // Hydrate the editable DOM once when switching on.
                      if (next) {
                        const stored = loadUnderlinesFromStorage();
                        const initial = stored || toSafeHtml(scriptText);
                        setScriptAnnotatedHtml(initial);
                        // Defer until after render.
                        queueMicrotask(() => {
                          if (scriptUnderlineRef.current) scriptUnderlineRef.current.innerHTML = initial;
                          if (scriptUnderlineRef.current && scriptCaretOffsetRef.current != null) {
                            _setTextCaretOffset(scriptUnderlineRef.current, scriptCaretOffsetRef.current);
                          }
                        });
                      } else {
                        // switching back to textarea: restore caret
                        queueMicrotask(() => {
                          const ta = scriptModalTextareaRef.current;
                          if (!ta) return;
                          ta.focus();
                          if (scriptCaretOffsetRef.current != null) {
                            ta.setSelectionRange(scriptCaretOffsetRef.current, scriptCaretOffsetRef.current);
                          }
                        });
                      }
                    }}
                  />
                  Modo subrayado
                </label>
                <Btn type="button" className="bg-slate-900 text-white hover:bg-slate-800" disabled={scriptIoLocked}
                  onClick={() => run("Guardar guion", async () => {
                    // Persist the underline markup locally so it survives refreshes.
                    if (scriptUnderlineMode && scriptUnderlineRef.current) {
                      const html = scriptUnderlineRef.current.innerHTML;
                      setScriptAnnotatedHtml(html);
                      saveUnderlinesToStorage(html);
                    }
                    await putJson(`/api/script`, { work: workApplied, text: scriptText });
                    await loadScript();
                    setScriptEditorFullscreen(false);
                  })}>
                  Guardar en sesión
                </Btn>
                <Btn type="button" className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setScriptEditorFullscreen(false)}>
                  Cerrar sin guardar
                </Btn>
              </div>
            </div>
            <div
              ref={scriptUnderlineRef}
              contentEditable={!scriptIoLocked}
              suppressContentEditableWarning
              spellCheck
              onKeyUp={() => {
                if (scriptUnderlineRef.current) {
                  scriptCaretOffsetRef.current = _getTextCaretOffset(scriptUnderlineRef.current);
                  if (scriptUnderlineMode) _toggleUnderlineSelection(scriptUnderlineRef.current);
                }
              }}
              onMouseUp={() => {
                if (scriptUnderlineRef.current) {
                  scriptCaretOffsetRef.current = _getTextCaretOffset(scriptUnderlineRef.current);
                  if (scriptUnderlineMode) _toggleUnderlineSelection(scriptUnderlineRef.current);
                }
              }}
              onInput={(e) => {
                const el = e.currentTarget;
                const html = el.innerHTML;
                setScriptAnnotatedHtml(html);
                saveUnderlinesToStorage(html);
                // Keep plain text in sync for saving to backend/pipeline.
                setScriptText(el.innerText);
                setScriptDirty(true);
                scriptCaretOffsetRef.current = _getTextCaretOffset(el);
              }}
              className={`min-h-0 flex-1 overflow-auto border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${
                scriptIoLocked ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"
              }`}
            />
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] leading-snug text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd>
              {" "}· «Cerrar sin guardar» descarta cambios. «Guardar en sesión» guarda y cierra.
              <span className="text-slate-400">
                {" "}· El subrayado se guarda localmente (no afecta a `guion.txt`).
              </span>
              {scriptIoLocked && <span className="font-medium text-amber-800"> Generando — solo lectura hasta que termine.</span>}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
