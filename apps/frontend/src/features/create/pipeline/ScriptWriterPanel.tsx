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
import { saveTextWithPicker, suggestedGuionFilename } from "../../../lib/saveTextFile";
import { patchJson, postJson, putJson } from "../../../services/api";
import type {
  ScriptWriterLibraryStore,
} from "../scriptWriter/useScriptWriterLibrary";
import {
  clampPipelineMinutes,
  PIPELINE_TARGET_MAX_MINUTES,
  PIPELINE_TARGET_MIN_MINUTES,
} from "../pipelineDuration";
import type { RunFn } from "../types";
import { TranscriptsSessionBanner } from "../shared/TranscriptsSessionBanner";
import { InferredFieldShell } from "../prompt/InferredFieldShell";
import { PipelineSection as Section } from "./PipelineSection";

// ── AI Script Writer Generator ───────────────────────────────────────────
function AIScriptWriterGenerator({
  onGenerated,
  provider,
  model,
  workApplied,
  lang,
}: {
  onGenerated: (t: Record<string, unknown>) => void | Promise<void>;
  provider: string;
  model: string;
  workApplied: string;
  lang: string;
}) {
  const [transcriptText, setTranscriptText] = useState("");
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionHint, setSessionHint] = useState(
    "Carga un documento o pega el contenido primero.",
  );
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!workApplied || fileName || transcriptText.trim()) return;
    let cancelled = false;

    setSessionHint("Cargando transcripts desde Analyse…");

    void fetch(
      `/api/session/transcripts?work=${encodeURIComponent(
        workApplied,
      )}&include_combined_text=true`,
    )
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as { combined_text?: string };
      })
      .then((data) => {
        if (cancelled) return;
        const combined = (data.combined_text ?? "").trim();
        if (combined) {
          setTranscriptText(combined);
          setSessionHint(
            "Transcripts cargados desde Analyse. Revisa el contenido y genera el template.",
          );
        } else {
          setSessionHint(
            "No se encontraron transcripts guardados en Analyse. Puedes subir o pegar uno aquí.",
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSessionHint(
            "No se pudo cargar transcripts desde Analyse. Puedes subir o pegar uno aquí.",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workApplied, fileName, transcriptText]);

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
        body: JSON.stringify({ transcript_text: transcriptText, provider, model, work: workApplied, lang }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(j.detail ?? `Error ${res.status}`);
      }
      const data = await res.json() as Record<string, unknown>;
      await onGenerated(data);
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
    <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold tracking-wider capitalize text-slate-900">Generador De Template Con IA</div>
          <div className="text-[11px] text-slate-500 mt-0.5">
            Carga las transcripciones del canal y Claude Sonnet analizará el estilo de guion y rellenará todos los campos del template automáticamente.
          </div>
        </div>
        <span className="shrink-0 rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-mono text-slate-700">
          Claude Sonnet
        </span>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Documento de transcripciones</label>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => fileRef.current?.click()}
            className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-900 hover:bg-slate-200 transition-colors">
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
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:border-sky-400 focus:outline-none resize-none"
        />
        <div className="mt-2 text-[11px] text-slate-500">{sessionHint}</div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>
      )}

      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-slate-500">Requiere <code className="rounded bg-slate-100 px-1 text-slate-700">ANTHROPIC_API_KEY</code> en .env</span>
        <div className="flex items-center gap-2">
          {loading && <span className="text-xs text-amber-600 animate-pulse">Claude analizando…</span>}
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
  llm_provider?: string;
  creative_provider?: string;
  creative_model?: string;
  anthropic_model?: string;
  production_provider?: string;
  openai_model?: string;
  ollama_model?: string;
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
  onAfterRun,
}: {
  run: RunFn;
  workApplied: string;
  locked: boolean;
  scriptStepState: string;
  library: ScriptWriterLibraryStore;
  onAfterRun?: () => void | Promise<void>;
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
  const [scriptEditorFullscreen, setScriptEditorFullscreen] = useState(false);
  const [scriptWriterMode, setScriptWriterMode] = useState<"choose" | "ia" | "manual">("choose");
  const scriptModalTextareaRef = useRef<HTMLTextAreaElement>(null);
  const scriptUnderlineRef = useRef<HTMLDivElement>(null);
  const underlineHydratedRef = useRef(false);
  const scriptTextRef = useRef("");
  const scriptCaretOffsetRef = useRef<number | null>(null);
  const [scriptPaths, setScriptPaths] = useState<{
    work: string;
    absolute_path: string;
    guion_relative: string;
    guion_absolute: string;
    guion_exists: boolean;
  } | null>(null);
  const [savingScript, setSavingScript] = useState(false);
  const [scriptOnDisk, setScriptOnDisk] = useState<{
    exists: boolean;
    source: string | null;
    chars: number;
  }>({ exists: false, source: null, chars: 0 });

  const loadScriptMeta = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/script-writer?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) {
        setScriptOnDisk({ exists: false, source: null, chars: 0 });
        return;
      }
      const j = (await r.json()) as {
        exists?: boolean;
        source?: string | null;
        chars?: number;
      };
      setScriptOnDisk({
        exists: !!j.exists,
        source: j.source ?? null,
        chars: typeof j.chars === "number" ? j.chars : 0,
      });
    } catch {
      setScriptOnDisk({ exists: false, source: null, chars: 0 });
    }
  }, [workApplied]);

  useEffect(() => {
    void loadScriptMeta();
  }, [loadScriptMeta, scriptStepState, workApplied]);

  const handleConfirmScript = () =>
    run("Confirmar guion", async () => {
      await postJson("/api/pipeline/script-writer/confirm", { work: workApplied });
      await onAfterRun?.();
      await refreshPipeline();
      await loadScriptMeta();
      await loadScript({ force: true });
    });

  useEffect(() => {
    if (lib.scriptWriterTemplateId) {
      setScriptWriterMode("choose");
    }
  }, [lib.scriptWriterTemplateId]);

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

  const plainTextFromStoredHtml = useCallback((html: string) => {
    if (!html.trim()) return "";
    const d = document.createElement("div");
    d.innerHTML = html;
    return d.innerText.replace(/\r\n/g, "\n");
  }, []);

  const editorHtmlForPlainText = useCallback(
    (plain: string) => {
      const stored = loadUnderlinesFromStorage();
      if (stored.trim() && plainTextFromStoredHtml(stored) === plain) {
        return stored;
      }
      if (stored.trim()) {
        try {
          localStorage.removeItem(underlineStorageKey);
        } catch {
          /* ignore */
        }
      }
      return toSafeHtml(plain);
    },
    [
      loadUnderlinesFromStorage,
      plainTextFromStoredHtml,
      toSafeHtml,
      underlineStorageKey,
    ],
  );

  const loadScriptPaths = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/work-dir?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) return;
      const j = (await r.json()) as {
        work?: string;
        absolute_path?: string;
        guion_relative?: string;
        guion_absolute?: string;
        guion_exists?: boolean;
      };
      if (!j.absolute_path) return;
      setScriptPaths({
        work: j.work ?? workApplied,
        absolute_path: j.absolute_path,
        guion_relative: j.guion_relative ?? "guion.txt",
        guion_absolute: j.guion_absolute ?? "",
        guion_exists: !!j.guion_exists,
      });
    } catch {
      setScriptPaths(null);
    }
  }, [workApplied]);

  const openScriptEditor = useCallback(() => {
    underlineHydratedRef.current = false;
    setScriptEditorFullscreen(true);
  }, []);

  const scriptTextForExport = useCallback(() => {
    if (scriptUnderlineMode && scriptUnderlineRef.current) {
      return scriptUnderlineRef.current.innerText.replace(/\r\n/g, "\n");
    }
    if (scriptEditorFullscreen && scriptModalTextareaRef.current) {
      return scriptModalTextareaRef.current.value;
    }
    return scriptText;
  }, [scriptText, scriptUnderlineMode, scriptEditorFullscreen]);

  const saveScriptToChosenFile = useCallback(async () => {
    const text = scriptTextForExport().trim();
    if (!text) return;
    const result = await saveTextWithPicker(
      text,
      suggestedGuionFilename(workApplied, kw),
    );
    if (result === "cancelled") return;
  }, [scriptTextForExport, workApplied, kw]);

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
    const totalMin = clampPipelineMinutes(minutes);
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
    const loaded = j.text ?? "";
    setScriptText(loaded);
    setScriptDirty(false);
  }, [workApplied]);

  const saveScriptToSession = useCallback(
    async (opts?: { closeEditor?: boolean }) => {
      setSavingScript(true);
      try {
        let textToSave = scriptText;
        if (scriptUnderlineMode && scriptUnderlineRef.current) {
          const html = scriptUnderlineRef.current.innerHTML;
          setScriptAnnotatedHtml(html);
          saveUnderlinesToStorage(html);
          textToSave = scriptUnderlineRef.current.innerText.replace(/\r\n/g, "\n");
          setScriptText(textToSave);
        }
        await putJson(`/api/script`, { work: workApplied, text: textToSave });
        await loadScript({ force: true });
        setManualEditMode(false);
        await loadScriptPaths();
        if (opts?.closeEditor) setScriptEditorFullscreen(false);
      } finally {
        setSavingScript(false);
      }
    },
    [
      scriptText,
      scriptUnderlineMode,
      workApplied,
      loadScript,
      saveUnderlinesToStorage,
      loadScriptPaths,
    ],
  );

  const prevScriptStepStateRef = useRef(scriptStepState);
  useEffect(() => {
    const prev = prevScriptStepStateRef.current;
    prevScriptStepStateRef.current = scriptStepState;
    if (prev === "running" && scriptStepState === "done") {
      void loadScript({ force: true });
      return;
    }
    void loadScript();
  }, [loadScript, scriptStepState, workApplied]);

  // When a template is applied, restore session defaults from it.
  useEffect(() => {
    if (!lib.scriptWriterTemplateId) return;
    if (lib.swSessionKeywords.trim()) setKw(lib.swSessionKeywords);
    if (lib.swSessionContext.trim()) setCtx(lib.swSessionContext);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lib.scriptWriterTemplateId, lib.swSessionKeywords, lib.swSessionContext]);

  useEffect(() => {
    void loadScriptPaths();
  }, [loadScriptPaths, scriptStepState, workApplied]);

  useEffect(() => {
    if (!scriptEditorFullscreen) {
      underlineHydratedRef.current = false;
      return;
    }

    // Hydrate once per open from el guion visible (no HTML antiguo de localStorage).
    if (!underlineHydratedRef.current) {
      underlineHydratedRef.current = true;
      const current = scriptTextRef.current;
      const initial = editorHtmlForPlainText(current);
      setScriptAnnotatedHtml(initial);
      queueMicrotask(() => {
        if (scriptUnderlineRef.current) {
          scriptUnderlineRef.current.innerHTML = initial;
        }
        const ta = scriptModalTextareaRef.current;
        if (ta && !scriptUnderlineMode) {
          ta.value = current;
          ta.focus();
        }
      });
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
  }, [
    scriptEditorFullscreen,
    loadUnderlinesFromStorage,
    scriptUnderlineMode,
    toSafeHtml,
    editorHtmlForPlainText,
  ]);

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
        const dRes = await fetch("/api/llm/defaults");
        const d = (await dRes.json()) as LlmDefaultsResponse;
        if (cancelled) return;
        setLlmDefaults(d);
        setOllamaNames([]);
        setOllamaListHint(null);
        if (!defaultsAppliedRef.current) {
          defaultsAppliedRef.current = true;
          setProvider("anthropic");
          setModel((prev) => {
            if (prev.trim()) return prev;
            return (
              d.creative_model?.trim() ||
              d.anthropic_model?.trim() ||
              "claude-sonnet-4-5"
            );
          });
        }
      } catch {
        if (!cancelled) {
          setOllamaListHint(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setModel]);

  const creativeModelPlaceholder =
    llmDefaults?.creative_model?.trim() ||
    llmDefaults?.anthropic_model?.trim() ||
    "claude-sonnet-4-5";

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
    <div className={`space-y-4 ${locked ? "opacity-90" : ""}`}>

      {/* ── Avisos ── */}
      {lockReason && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          <span className="font-semibold">Generando.</span> {lockReason} Espera a que termine antes de guardar el guion.
          Para cambiar plantilla o regenerar desde cero usa <strong>Reset</strong> en la pipeline.
        </div>
      )}

      {locked && !scriptIoLocked ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900">
          Guion <strong>confirmado</strong> ({scriptOnDisk.source ?? "guion.txt"},{" "}
          {scriptOnDisk.chars.toLocaleString()} caracteres). El paso está en <em>done</em>.
        </div>
      ) : scriptOnDisk.exists && scriptStepState !== "done" ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Hay guion en <strong>{scriptOnDisk.source}</strong> pero el paso está en <strong>idle</strong>.
          Confírmalo para marcar <em>done</em> sin volver a ejecutar Start step.
        </div>
      ) : !scriptOnDisk.exists ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
          Aún no hay guion en disco. Usa Start step, pega texto y guarda, o confirma tras generar.
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Btn
          type="button"
          className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40"
          disabled={locked || scriptIoLocked || !scriptOnDisk.exists}
          onClick={() => void handleConfirmScript()}
        >
          Confirmar guion (bloquear)
        </Btn>
        <Btn
          type="button"
          className="border border-slate-200 bg-slate-50 text-slate-700"
          onClick={() => void loadScriptMeta()}
        >
          Recargar estado
        </Btn>
      </div>

      {locked && !scriptIoLocked && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
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
              <span className="text-[11px] text-amber-700">
                Modo edición activo: al guardar el guion se volverá a bloquear.
              </span>
            )}
          </div>
        </div>
      )}

      <TranscriptsSessionBanner workApplied={workApplied} />

      <fieldset disabled={effectiveLocked} className="min-w-0 space-y-3 border-0 p-0">

        {/* ── Template selector ── */}
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3.5">
            <label className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-slate-500">
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
              className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-900 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
            >
              <option value="">(nuevo template)</option>
              {lib.scriptWriterTemplates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-2 px-4 py-4 sm:px-5">
            <Btn
              type="button"
              className="border border-slate-200 bg-slate-100 text-slate-900 hover:bg-slate-200"
              onClick={() =>
                run("Reiniciar fragmentación y reiniciar creación", async () => {
                  if (!confirm("¿Borrar estado de fragmentación y reiniciar la creación del guion?")) return;
                  await postJson("/api/script-fragmentation/reset", { work: workApplied });
                  setScriptFragmentIndex(null);
                  setScriptText("");
                  setScriptDirty(false);
                  setManualEditMode(false);
                  await loadFragState();
                  await refreshPipeline();
                })
              }
            >
              Reiniciar
            </Btn>
            <Btn type="button" className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50" disabled={!lib.swName.trim()}
              onClick={() => run("Guardar template Script Writer", async () => { await lib.saveTemplate(); })}>
              Save
            </Btn>
            <Btn type="button" className="border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-40"
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

        {/* ── Generador IA / Manual: nuevo template ── */}
        {!lib.scriptWriterTemplateId && !effectiveLocked && (
          <> 
            {scriptWriterMode === "choose" ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                <div className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-900">
                  CREAR NUEVO TEMPLATE
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setScriptWriterMode("ia")}
                    className="flex flex-col items-start rounded-2xl border border-violet-200 bg-violet-50 p-4 text-left transition hover:border-violet-300 hover:bg-violet-100"
                  >
                    <span className="text-sm font-semibold text-slate-900">Generador con IA</span>
                    <p className="mt-2 text-sm text-slate-600">
                      Carga transcripts y deja que la IA rellene automáticamente los campos del template.
                    </p>
                    <span className="mt-3 inline-flex items-center rounded-full bg-violet-100 px-2.5 py-1 text-[11px] font-medium text-violet-700">
                      Recomendado
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setScriptWriterMode("manual")}
                    className="flex flex-col items-start rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    <span className="text-sm font-semibold text-slate-900">Manual</span>
                    <p className="mt-2 text-sm text-slate-600">
                      Rellena manualmente los campos del template y ajusta el guion desde cero.
                    </p>
                    <span className="mt-3 inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-700">
                      Modo manual
                    </span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <div>
                    <div className="text-sm font-semibold uppercase tracking-wide text-slate-900">
                      {scriptWriterMode === "ia" ? "GENERADOR DE TEMPLATE CON IA" : "TEMPLATE MANUAL"}
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      {scriptWriterMode === "ia"
                        ? "Carga los transcripts y deja que la IA rellene los apartados. Después podrás revisar y editar antes del Start step."
                        : "Rellena los campos a mano. Puedes volver a las opciones de creación en cualquier momento."}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setScriptWriterMode("choose")}
                    className="text-sm font-medium text-slate-700 hover:text-slate-900"
                  >
                    Volver a opciones
                  </button>
                </div>
                {scriptWriterMode === "ia" && (
                  <AIScriptWriterGenerator
                    provider="anthropic"
                    model={model}
                    workApplied={workApplied}
                    lang={lang}
                    onGenerated={async (data) => {
                      lib.applyTemplateFields(data as Parameters<typeof lib.applyTemplateFields>[0]);
                      await lib.saveTemplate();
                    }}
                  />
                )}
              </div>
            )}
          </>
        )}

        {/* ── Template settings ── */}
        <Section id="sw-template" title="CONFIGURACIÓN DEL TEMPLATE" description="Nombre, ritmo, densidad narrativa y estructura de actos del guion." theme="light">
          <div className="space-y-3">
            <div>
              <Label>Nombre</Label>
              <Input value={lib.swName} onChange={(e) => lib.setSwName(e.target.value)} placeholder="Ej: Long-form finanzas · ritmo documental" />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <div className="flex items-start gap-2">
                  <Label>Ritmo (VO)</Label>
                  <span className="group relative inline-flex items-start">
                    <span
                      className="relative -top-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 bg-slate-100 text-[9px] font-semibold text-slate-600"
                      aria-label="Información sobre cómo influye el ritmo en el guion"
                      role="button"
                    >i</span>
                    <span className="pointer-events-none absolute left-0 top-full z-20 hidden w-[18rem] rounded-md border border-slate-300 bg-slate-900 px-3 py-2 text-[10px] leading-5 text-slate-100 shadow-lg opacity-0 transition-opacity duration-150 group-hover:block group-hover:opacity-100">
                      Ajusta la velocidad y estilo de voz del guion: corto hace el texto más directo y rápido, largo lo convierte en una narración más pausada y detallada.
                    </span>
                  </span>
                </div>
                <Select value={lib.swPacing} onChange={(e) => lib.setSwPacing(e.target.value as typeof lib.swPacing)}>
                  <option value="">(sin override: hereda de Prompt)</option>
                  <option value="short">Corto / rápido</option>
                  <option value="mixed">Mixto</option>
                  <option value="long">Largo / documental</option>
                </Select>
              </div>
              <div>
                <div className="flex items-start gap-2">
                  <Label>Densidad de datos</Label>
                  <span className="group relative inline-flex items-start">
                    <span
                      className="relative -top-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 bg-slate-100 text-[9px] font-semibold text-slate-600"
                      aria-label="Información sobre cómo influye la densidad de datos en el guion"
                      role="button"
                    >i</span>
                    <span className="pointer-events-none absolute left-0 top-full z-20 hidden w-[18rem] rounded-md border border-slate-300 bg-slate-900 px-3 py-2 text-[10px] leading-5 text-slate-100 shadow-lg opacity-0 transition-opacity duration-150 group-hover:block group-hover:opacity-100">
                      Controla cuánta información incluye el guion: baja prioriza historia y metáforas, alta incluye más cifras, datos y detalles técnicos.
                    </span>
                  </span>
                </div>
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
            
            {lib.swStructure === "four_act" && fourActPreview && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-900">Vista previa de 4 actos</div>
                  <p className="text-xs text-slate-500">
                    Duración del pipeline: {clampPipelineMinutes(minutes)} min (objetivo{" "}
                    {PIPELINE_TARGET_MIN_MINUTES}–{PIPELINE_TARGET_MAX_MINUTES}).
                  </p>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr>
                        <th className="pb-2 text-left font-semibold text-slate-700">Acto</th>
                        <th className="pb-2 text-left font-semibold text-slate-700">Descripción</th>
                        <th className="pb-2 text-left font-semibold text-slate-700">%</th>
                        <th className="pb-2 text-left font-semibold text-slate-700">Min</th>
                        <th className="pb-2 text-left font-semibold text-slate-700">Palabras</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fourActPreview.map((row, i) => (
                        <tr key={i} className="border-t border-slate-200 text-slate-700">
                          <td className="py-2 pr-3 font-mono text-slate-500">{["I", "II", "III", "IV"][i]}</td>
                          <td className="py-2 pr-3">{row.label}</td>
                          <td className="py-2 pr-3 font-mono">{row.pct.toFixed(0)}%</td>
                          <td className="py-2 pr-3 font-mono">{row.min.toFixed(1)}</td>
                          <td className="py-2 font-mono">~{row.words}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div>
              <Label>Texto extra → system (prompt interno)</Label>
              <InferredFieldShell showSectionLabel>
                <ExpandableTextArea
                  value={lib.swSystem}
                  onChange={lib.setSwSystem}
                  placeholder="Reglas extra para la generación del guion (se añaden al system del LLM tras el template de Prompt)."
                  modalTitle="Script Writer · Texto extra → system (prompt interno)"
                  variant="inferred"
                />
              </InferredFieldShell>
            </div>
            <div>
              <Label>Texto extra → user (prompt interno)</Label>
              <InferredFieldShell showSectionLabel>
                <ExpandableTextArea
                  value={lib.swUser}
                  onChange={lib.setSwUser}
                  placeholder="Preferencias de formato, ejemplos a evitar, compliance…"
                  modalTitle="Script Writer · Texto extra → user (prompt interno)"
                  variant="inferred"
                />
              </InferredFieldShell>
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
                <InferredFieldShell showSectionLabel={false} className="p-0">
                  <ExpandableTextArea
                    label="Contexto"
                    value={ctx}
                    onChange={(v) => {
                      setCtx(v);
                      lib.setSwSessionContext(v);
                    }}
                    placeholder="Público, tono, datos que deben aparecer…"
                    modalTitle="Contexto del Script Writer"
                    variant="inferred"
                  />
                </InferredFieldShell>
              </div>
            </div>
          </div>
        </Section>

        {/* ── Sesión + Fragmentación (switch) ── */}
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex w-full items-start justify-between gap-3 bg-slate-50 px-4 py-3 text-left">
            <div className="flex min-w-0 flex-1 flex-col gap-y-0.5">
              <div className="flex items-center gap-2">
                <span className="shrink-0 text-sm font-semibold tracking-wider uppercase text-slate-900">
                  SESIÓN DE EJECUCIÓN Y FRAGMENTACIÓN
                </span>
                <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 font-mono">
                  opcional
                </span>
              </div>
              <span className="text-[11px] leading-snug text-slate-500 font-normal">
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
            <div className="border-t border-slate-200 bg-slate-50 px-4 pb-4 pt-3 space-y-4">
              {/* Ejecución */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>Idioma</Label>
                  <Select
                    value={lang}
                    disabled
                    className="cursor-not-allowed bg-slate-100 text-slate-700"
                    onChange={() => {}}
                  >
                    <option value="es">es</option>
                    <option value="en">en</option>
                  </Select>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Lo fija <strong>Topic Generator → Idioma de salida</strong> ({lang === "en" ? "English" : "Español"}).
                  </p>
                </div>
                <div>
                  <Label>Duración orientativa (min)</Label>
                  <Input type="number" step={0.5} min={1} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
                </div>
                <div>
                  <Label>Proveedor LLM</Label>
                  <Input
                    value="Anthropic (Claude)"
                    readOnly
                    className="bg-slate-100 text-slate-700"
                  />
                  <p className="mt-1 text-[11px] text-slate-500">
                    Topic Generator, Prompt y Script Writer usan Anthropic. Metadata y routers usan OpenAI.
                  </p>
                </div>
                <div>
                  <Label>Modelo Claude</Label>
                  <Input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder={creativeModelPlaceholder}
                  />
                </div>
              </div>

              {/* Fragmentación */}
              <div className="space-y-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
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
                  {lib.swChunking === "sequential_fragments" && <p className="mt-1 text-[11px] text-slate-500">{structureSequentialCopy.helperSequential}</p>}
                </div>

                {lib.swChunking === "sequential_fragments" && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 space-y-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Progreso por fragmentos</div>
                    <p className="text-[11px] text-slate-500">{structureSequentialCopy.weightsIntro}</p>
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
                      <Btn type="button" className="border border-slate-200 bg-slate-100 text-slate-900 hover:bg-slate-200" onClick={() => void loadFragState()}>Refrescar</Btn>
                      <Btn type="button" className="border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                        onClick={() => run("Reiniciar fragmentación", async () => {
                          if (!confirm("¿Borrar estado y chunks guardados?")) return;
                          await postJson(`/api/script-fragmentation/reset`, { work: workApplied });
                          setScriptFragmentIndex(null);
                          setScriptText("");
                          setScriptDirty(false);
                          setManualEditMode(false);
                          await loadFragState();
                          await refreshPipeline();
                        })}>
                        Reiniciar
                      </Btn>
                    </div>
                    {!fragExists ? (
                      <p className="text-[11px] text-slate-500">Sin estado en disco aún. Aparecerá tras el primer Start step.</p>
                    ) : (
                      <ul className="space-y-2 border-t border-slate-200 pt-3">
                        {fragSteps.map((s, i) => (
                          <li key={`${s.id}-${i}`} className="flex flex-wrap items-center gap-2">
                            <span className="w-6 font-mono text-[11px] text-slate-400">{i}</span>
                            <span className="min-w-[120px] flex-1 text-slate-900 font-medium">{s.label}</span>
                            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">{s.status}</span>
                            <label className="flex cursor-pointer items-center gap-1 text-[11px] text-slate-700">
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

      </fieldset>

      {/* ── Guion ── */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold tracking-wider capitalize text-slate-900">Salida · Guion</div>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Texto de <code className="rounded bg-slate-100 px-1">guion.txt</code> en esta sesión. No es el preview del paso Prompt (ahí solo ves instrucciones al LLM).
              {lib.swChunking === "sequential_fragments"
                ? " Con fragmentación, aquí va el guion ensamblado (outline + fragmentos completados), no solo el último fragmento."
                : null}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Btn
              type="button"
              className="border border-slate-200 bg-slate-900 text-white hover:bg-slate-800"
              disabled={scriptIoLocked || !scriptTextForExport().trim()}
              onClick={() =>
                run("Guardar en…", async () => {
                  await saveScriptToChosenFile();
                })
              }
            >
              Guardar en…
            </Btn>
            <Btn
              type="button"
              className="border border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
              disabled={scriptIoLocked || savingScript || !scriptText.trim()}
              onClick={() =>
                run("Guardar en sesión", async () => {
                  await saveScriptToSession();
                })
              }
            >
              {savingScript ? "Guardando…" : "Guardar en sesión"}
            </Btn>
            <Btn
              type="button"
              className="border border-slate-200 bg-slate-100 text-slate-900 hover:bg-slate-200"
              onClick={() => void loadScript({ force: true })}
            >
              Recargar desde disco
            </Btn>
            <Btn
              type="button"
              className="border border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
              onClick={() =>
                run("Abrir carpeta de sesión", async () => {
                  await postJson("/api/work-dir/reveal", {
                    work: workApplied,
                    highlight: "guion.txt",
                  });
                })
              }
            >
              Abrir carpeta
            </Btn>
          </div>
        </div>
        {scriptPaths ? (
          <p className="text-[11px] text-slate-500">
            <span className="font-medium text-slate-600">Ruta:</span>{" "}
            <code className="break-all rounded bg-slate-100 px-1 text-slate-700">
              {scriptPaths.guion_absolute || `${scriptPaths.absolute_path}/${scriptPaths.guion_relative}`}
            </code>
            {!scriptPaths.guion_exists ? (
              <span className="ml-1 text-amber-700"> (aún no existe en disco)</span>
            ) : null}
          </p>
        ) : null}
        <div role="button" tabIndex={0} aria-label="Abrir editor de guion a pantalla completa"
          onClick={openScriptEditor}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openScriptEditor(); } }}
          className={`min-h-[200px] w-full cursor-pointer rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left font-mono text-xs leading-relaxed shadow-sm outline-none transition hover:border-slate-300 ${scriptText.trim() ? "text-slate-900" : "text-slate-500"}`}>
          <span className="block max-h-[280px] overflow-y-auto whitespace-pre-wrap">
            {scriptText.trim() ? scriptText : "Tras Start step aparecerá el guion aquí. Pulsa para abrir el editor completo."}
          </span>
        </div>
        <p className="text-[11px] text-slate-500">
          <strong>Guardar en…</strong> abre el diálogo del sistema para elegir carpeta y nombre del archivo.
          <strong> Guardar en sesión</strong> actualiza <code className="rounded bg-slate-100 px-1">guion.txt</code> del
          proyecto (necesario para Hook Router, TTS y el resto del pipeline).
        </p>
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

                      if (!next && scriptModalTextareaRef.current) {
                        setScriptText(scriptModalTextareaRef.current.value);
                      }

                      setScriptUnderlineMode(next);
                      if (next) {
                        const plain =
                          scriptModalTextareaRef.current?.value ?? scriptText;
                        const initial = editorHtmlForPlainText(plain);
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
                <Btn
                  type="button"
                  className="border border-slate-200 bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                  disabled={scriptIoLocked || !scriptTextForExport().trim()}
                  onClick={() => run("Guardar en…", async () => void saveScriptToChosenFile())}
                >
                  Guardar en…
                </Btn>
                <Btn
                  type="button"
                  className="bg-violet-600 text-white hover:bg-violet-500"
                  disabled={scriptIoLocked || savingScript}
                  onClick={() =>
                    run("Guardar en sesión", async () => {
                      await saveScriptToSession({ closeEditor: true });
                    })
                  }
                >
                  {savingScript ? "Guardando…" : "Guardar en sesión y cerrar"}
                </Btn>
                <Btn
                  type="button"
                  className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                  onClick={() =>
                    run("Abrir carpeta", async () => {
                      await postJson("/api/work-dir/reveal", {
                        work: workApplied,
                        highlight: "guion.txt",
                      });
                    })
                  }
                >
                  Abrir carpeta
                </Btn>
                <Btn
                  type="button"
                  className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                  onClick={() => {
                    void loadScript({ force: true });
                    setScriptEditorFullscreen(false);
                  }}
                >
                  Cerrar sin guardar
                </Btn>
              </div>
            </div>
            {scriptUnderlineMode ? (
              <div
                ref={scriptUnderlineRef}
                contentEditable={!scriptIoLocked}
                suppressContentEditableWarning
                spellCheck
                onKeyUp={() => {
                  if (scriptUnderlineRef.current) {
                    scriptCaretOffsetRef.current = _getTextCaretOffset(scriptUnderlineRef.current);
                    _toggleUnderlineSelection(scriptUnderlineRef.current);
                  }
                }}
                onMouseUp={() => {
                  if (scriptUnderlineRef.current) {
                    scriptCaretOffsetRef.current = _getTextCaretOffset(scriptUnderlineRef.current);
                    _toggleUnderlineSelection(scriptUnderlineRef.current);
                  }
                }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  const html = el.innerHTML;
                  setScriptAnnotatedHtml(html);
                  saveUnderlinesToStorage(html);
                  setScriptText(el.innerText.replace(/\r\n/g, "\n"));
                  setScriptDirty(true);
                  scriptCaretOffsetRef.current = _getTextCaretOffset(el);
                }}
                className={`min-h-0 flex-1 overflow-auto border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${
                  scriptIoLocked ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"
                }`}
              />
            ) : (
              <textarea
                ref={scriptModalTextareaRef}
                value={scriptText}
                readOnly={scriptIoLocked}
                onChange={(e) => {
                  setScriptText(e.target.value);
                  setScriptDirty(true);
                }}
                className={`min-h-0 flex-1 resize-none border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${
                  scriptIoLocked ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"
                }`}
                spellCheck
              />
            )}
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
