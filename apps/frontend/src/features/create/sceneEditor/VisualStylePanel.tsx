import { useCallback, useEffect, useState } from "react";
import { Btn, Input, Label, Select } from "../../../components/ui";
import { deleteReq, postJson, putJson } from "../../../services/api";
import {
  EMPTY_SCENE_VISUAL_SETTINGS,
  VISUAL_EXPRESSION_PLANNER_ES,
  VISUAL_PLANNER_VALIDATIONS_ES,
  type SceneVisualSettings,
  type VisualEffectiveRulesPreview,
  type VisualPlannerConfig,
} from "./sceneVisualSettings";
import {
  ALEX_PRESET_ID,
  type VisualStylePresetFull,
  type VisualStylePresetSummary,
} from "./visualStylePresets";

type VisualStyleTheme = "light" | "dark";

const THEME: Record<
  VisualStyleTheme,
  {
    shell: string;
    title: string;
    body: string;
    label: string;
    hint: string;
    input: string;
    cardSky: string;
    cardViolet: string;
    cardEmerald: string;
    code: string;
    btn: string;
    saved: string;
    loading: string;
    select: string;
  }
> = {
  light: {
    shell: "space-y-3 rounded-xl border border-sky-200 bg-sky-50/80 px-3 py-3",
    title: "text-[13px] font-semibold text-sky-950",
    body: "text-[11px] text-sky-800",
    label: "text-[11px] font-semibold text-sky-900",
    hint: "text-[10px] text-sky-700",
    input:
      "mt-1 w-full resize-y rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-[11px] leading-relaxed",
    cardSky: "rounded-lg border border-sky-100 bg-white/90 px-2.5 py-2",
    cardViolet: "rounded-lg border border-violet-200 bg-violet-50/80 px-2.5 py-2.5",
    cardEmerald: "rounded-lg border border-emerald-200 bg-emerald-50/80 px-2.5 py-2.5",
    code: "rounded bg-white/80 px-1",
    btn: "bg-sky-700 text-white hover:bg-sky-600 disabled:opacity-50",
    saved: "text-[11px] text-emerald-700",
    loading: "text-[12px] text-slate-500",
    select: "ml-2 rounded border border-sky-200 bg-white px-2 py-1 text-[11px]",
  },
  dark: {
    shell: "space-y-3 rounded-lg border border-slate-600 bg-slate-900/40 px-3 py-3",
    title: "text-[13px] font-semibold text-slate-100",
    body: "text-[11px] text-slate-400",
    label: "text-[11px] font-semibold text-slate-200",
    hint: "text-[10px] text-slate-500",
    input:
      "mt-1 w-full resize-y rounded-lg border border-slate-600 bg-slate-800 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-slate-200",
    cardSky: "rounded-lg border border-slate-600 bg-slate-800/60 px-2.5 py-2",
    cardViolet: "rounded-lg border border-violet-500/30 bg-violet-950/30 px-2.5 py-2.5",
    cardEmerald: "rounded-lg border border-emerald-500/30 bg-emerald-950/25 px-2.5 py-2.5",
    code: "rounded bg-slate-700 px-1 text-slate-300",
    btn: "bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50",
    saved: "text-[11px] text-emerald-400",
    loading: "text-[12px] text-slate-500",
    select:
      "ml-2 rounded border border-slate-600 bg-slate-700 px-2 py-1 text-[11px] text-slate-200",
  },
};

const DRAFT_PRESET_ID = "__draft__";

function FieldStatusBadge({
  value,
  theme,
}: {
  value: string;
  theme: VisualStyleTheme;
}) {
  const empty = !value.trim();
  return (
    <span
      className={
        empty
          ? theme === "dark"
            ? "rounded bg-amber-950/50 px-1.5 py-0.5 text-[10px] font-medium text-amber-200 ring-1 ring-amber-500/40"
            : "rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 ring-1 ring-amber-200"
          : theme === "dark"
            ? "rounded bg-emerald-950/40 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300 ring-1 ring-emerald-500/30"
            : "rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800 ring-1 ring-emerald-200"
      }
    >
      {empty ? "Vacío → builtin del servidor" : `Personalizado · ${value.trim().length} caracteres`}
    </span>
  );
}

function MotorRuleField({
  label,
  hint,
  value,
  onChange,
  builtinText,
  theme,
  t,
  minH = "min-h-[80px]",
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  builtinText?: string;
  theme: VisualStyleTheme;
  t: (typeof THEME)["dark"];
  minH?: string;
}) {
  const empty = !value.trim();
  return (
    <label className="mt-2 block">
      <div className="flex flex-wrap items-center gap-2">
        <span className={t.label}>{label}</span>
        <FieldStatusBadge value={value} theme={theme} />
      </div>
      <p className={`mt-0.5 ${t.hint}`}>{hint}</p>
      <textarea
        className={`${t.input} mt-1 ${minH} font-mono text-[10px]`}
        value={value}
        placeholder="Vacío = no hay nada guardado aquí; el servidor usa su texto por defecto (ver debajo)."
        onChange={(e) => onChange(e.target.value)}
      />
      {empty && builtinText ? (
        <details className="mt-1.5 rounded border border-dashed border-slate-500/50 bg-slate-900/20 px-2 py-1.5 dark:bg-slate-800/40">
          <summary className={`cursor-pointer text-[10px] font-medium ${t.hint}`}>
            Texto builtin que aplicará el servidor (solo lectura)
          </summary>
          <pre
            className={`mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-[10px] leading-relaxed ${theme === "dark" ? "text-slate-400" : "text-slate-600"}`}
          >
            {builtinText}
          </pre>
        </details>
      ) : null}
    </label>
  );
}

function presetFieldsFromSettings(s: SceneVisualSettings) {
  return {
    base_style_en: s.base_style_en,
    protagonist_en: s.protagonist_en,
    protagonist_wardrobe_en: s.protagonist_wardrobe_en,
    protagonist_action_rules_en: s.protagonist_action_rules_en,
    protagonist_expressions_en: s.protagonist_expressions_en,
    avoid_en: s.avoid_en,
    planner_extra_rules_en: s.planner_extra_rules_en,
    gemini_continuity_prefix_en: s.gemini_continuity_prefix_en,
    auto_avoid_supplement_en: s.auto_avoid_supplement_en,
    aspect_ratio: s.aspect_ratio,
    output_spec: s.output_spec,
  };
}

export function VisualStylePanel({
  work,
  onSaved,
  theme = "light",
  presetId = ALEX_PRESET_ID,
  onPresetIdChange,
  showPresetControls = false,
}: {
  work: string;
  onSaved?: () => void;
  theme?: VisualStyleTheme;
  presetId?: string;
  onPresetIdChange?: (id: string) => void;
  showPresetControls?: boolean;
}) {
  const t = THEME[theme];
  const [settings, setSettings] = useState<SceneVisualSettings>(EMPTY_SCENE_VISUAL_SETTINGS);
  const [plannerConfig, setPlannerConfig] = useState<VisualPlannerConfig | null>(null);
  const [presetList, setPresetList] = useState<VisualStylePresetSummary[]>([]);
  const [isDraftNew, setIsDraftNew] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [rulesPreview, setRulesPreview] = useState<VisualEffectiveRulesPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const loadPresets = useCallback(async () => {
    const r = await fetch(`/api/visual-style-presets?work=${encodeURIComponent(work)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { presets: VisualStylePresetSummary[] };
    setPresetList(j.presets ?? []);
  }, [work]);

  const loadWorkSettings = useCallback(async () => {
    const [settingsRes, configRes] = await Promise.all([
      fetch(`/api/visual/style-settings?work=${encodeURIComponent(work)}`),
      fetch(`/api/visual/planner-config?work=${encodeURIComponent(work)}`),
    ]);
    if (settingsRes.ok) {
      const data = (await settingsRes.json()) as SceneVisualSettings;
      setSettings({
        ...EMPTY_SCENE_VISUAL_SETTINGS,
        ...data,
        aspect_ratio: data.aspect_ratio || "16:9",
        output_spec: data.output_spec || "2K output",
      });
    }
    const rulesRes = await fetch(`/api/visual/effective-rules?work=${encodeURIComponent(work)}`);
    if (rulesRes.ok) {
      setRulesPreview((await rulesRes.json()) as VisualEffectiveRulesPreview);
    }
    if (configRes.ok) {
      setPlannerConfig((await configRes.json()) as VisualPlannerConfig);
    }
  }, [work]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        if (showPresetControls) {
          const pr = await fetch(`/api/visual-style-presets?work=${encodeURIComponent(work)}`);
          if (!pr.ok) {
            const err = (await pr.json().catch(() => ({}))) as { detail?: string };
            throw new Error(typeof err.detail === "string" ? err.detail : `Presets HTTP ${pr.status}`);
          }
          const pj = (await pr.json()) as { presets: VisualStylePresetSummary[] };
          if (!cancelled) setPresetList(pj.presets ?? []);
        }
        await loadWorkSettings();
      } catch (e) {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : "Error al cargar estilo visual");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [work, showPresetControls, loadWorkSettings]);

  const applyPreset = async (id: string) => {
    await postJson("/api/visual-style-presets/apply", { work, preset_id: id });
    onPresetIdChange?.(id);
    await loadWorkSettings();
  };

  const startNewStyleDraft = () => {
    setIsDraftNew(true);
    setNewPresetName("");
    setSettings({ ...EMPTY_SCENE_VISUAL_SETTINGS });
    setRulesPreview(null);
    onPresetIdChange?.("");
  };

  const handlePresetSelect = async (id: string) => {
    if (id === DRAFT_PRESET_ID) return;
    if (!id || (id === presetId && !isDraftNew)) return;
    setIsDraftNew(false);
    setLoading(true);
    try {
      await applyPreset(id);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error al cargar estilo");
    } finally {
      setLoading(false);
    }
  };


  const deleteCurrentPreset = async () => {
    const current = presetList.find((p) => p.id === presetId);
    if (!current || current.bundled) return;
    if (!confirm(`¿Eliminar el estilo "${current.name}"?`)) return;
    try {
      await deleteReq(`/api/visual-style-presets/${encodeURIComponent(presetId)}`);
      await loadPresets();
      await applyPreset(ALEX_PRESET_ID);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error al eliminar estilo");
    }
  };

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      if (isDraftNew) {
        const name = newPresetName.trim();
        if (!name) {
          alert("Escribe un nombre para el nuevo estilo guardado.");
          return;
        }
        const created = (await postJson("/api/visual-style-presets", {
          name,
          ...presetFieldsFromSettings(settings),
        })) as VisualStylePresetFull;
        setIsDraftNew(false);
        await loadPresets();
        await applyPreset(created.id);
        setSaved(true);
        onSaved?.();
        return;
      }

      const r = await fetch("/api/visual/style-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work, ...settings }),
      });
      if (!r.ok) {
        const err = (await r.json().catch(() => ({}))) as { detail?: string };
        throw new Error(typeof err.detail === "string" ? err.detail : "Error al guardar");
      }
      if (showPresetControls && presetId) {
        await putJson(`/api/visual-style-presets/${encodeURIComponent(presetId)}`, {
          ...presetFieldsFromSettings(settings),
        });
      }
      await loadWorkSettings();
      setSaved(true);
      onSaved?.();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error al guardar estilo");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className={t.loading}>Cargando estilo visual…</p>;
  }

  if (loadError) {
    return (
      <div className={`rounded-lg border px-3 py-2 text-[11px] ${theme === "dark" ? "border-rose-500/40 bg-rose-950/30 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-900"}`}>
        <p>{loadError}</p>
        <Btn
          type="button"
          className={`mt-2 ${t.btn}`}
          onClick={() => {
            setLoadError(null);
            setLoading(true);
            void (async () => {
              try {
                if (showPresetControls) await loadPresets();
                await loadWorkSettings();
              } catch (e) {
                setLoadError(e instanceof Error ? e.message : "Error al cargar");
              } finally {
                setLoading(false);
              }
            })();
          }}
        >
          Reintentar
        </Btn>
      </div>
    );
  }

  const selectedPreset = presetList.find((p) => p.id === presetId);
  const selectValue = isDraftNew ? DRAFT_PRESET_ID : presetId;

  return (
    <div className={t.shell}>
      <div>
        <h4 className={t.title}>Estilo visual · Nano Banana 2</h4>
        <p className={`mt-1 ${t.body}`}>
          El <strong className="text-inherit">estilo base</strong> se añade al prompt completo. El Scene Editor y las{" "}
          <strong className="text-inherit">miniaturas en Metadata</strong> usan estos ajustes. Las{" "}
          <strong className="text-inherit">reglas de pose</strong> van al planner y a la cola Gemini (imágenes 2+).
        </p>
      </div>

      {showPresetControls ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-[200px] flex-1">
              <Label className={theme === "dark" ? "!text-slate-200" : undefined}>Estilo guardado</Label>
              <Select
                value={selectValue}
                onChange={(e) => void handlePresetSelect(e.target.value)}
                className={theme === "dark" ? "!mt-1 !border-slate-600 !bg-slate-700 !text-slate-200" : "!mt-1"}
              >
                {isDraftNew ? (
                  <option value={DRAFT_PRESET_ID}>— Nuevo estilo (borrador) —</option>
                ) : null}
                {presetList.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.bundled ? "★ " : ""}
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <Btn
              type="button"
              className={
                theme === "dark"
                  ? "shrink-0 border border-violet-500/50 bg-violet-950/40 text-violet-200 hover:bg-violet-900/50"
                  : "shrink-0 border border-sky-300 bg-white text-sky-900 hover:bg-sky-50"
              }
              onClick={startNewStyleDraft}
            >
              + Nuevo estilo
            </Btn>
            {selectedPreset && !selectedPreset.bundled && !isDraftNew ? (
            <Btn
              type="button"
              className={
                theme === "dark"
                  ? "shrink-0 border border-rose-500/40 bg-rose-950/30 text-rose-200"
                  : "shrink-0 border border-rose-300 bg-rose-50 text-rose-900"
              }
              onClick={() => void deleteCurrentPreset()}
            >
              Borrar
            </Btn>
          ) : null}
          </div>
          {isDraftNew ? (
            <div>
              <Label className={theme === "dark" ? "!text-slate-200" : undefined}>Nombre del nuevo estilo *</Label>
              <Input
                value={newPresetName}
                onChange={(e) => setNewPresetName(e.target.value)}
                placeholder="Ej.: Documental frío, Cartoon pastel…"
                className={
                  theme === "dark"
                    ? "!mt-1 !border-slate-600 !bg-slate-700 !text-slate-200"
                    : "!mt-1"
                }
              />
              <p className={`mt-1 ${t.hint}`}>
                Los campos empiezan vacíos. Rellena lo que quieras y pulsa <strong className="text-inherit">Guardar estilo</strong> para crear el preset.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      {plannerConfig?.planner_injects?.length ? (
        <div className={t.cardSky}>
          <p className={`text-[10px] font-semibold uppercase tracking-wide ${t.label}`}>
            Dónde entra cada campo
          </p>
          <ul className={`mt-1 list-inside list-disc space-y-0.5 text-[10px] ${theme === "dark" ? "text-slate-300" : "text-sky-900"}`}>
            {plannerConfig.planner_injects.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <label className="block">
        <span className={t.label}>Estilo base (inglés) *</span>
        <textarea
          className={`${t.input} min-h-[72px] font-mono`}
          value={settings.base_style_en}
          onChange={(e) => setSettings((s) => ({ ...s, base_style_en: e.target.value }))}
          placeholder="Ej.: Cinematic documentary, muted warm palette, 35mm grain, shallow DOF…"
        />
      </label>

      <label className="block">
        <span className={t.label}>Protagonista — cara (inglés)</span>
        <p className={t.hint}>
          Rasgos faciales del personaje recurrente. La ropa y pelo van en el campo de abajo.
        </p>
        <textarea
          className={`${t.input} min-h-[64px]`}
          value={settings.protagonist_en}
          onChange={(e) => setSettings((s) => ({ ...s, protagonist_en: e.target.value }))}
        />
      </label>

      <label className="block">
        <span className={t.label}>Protagonista — ropa y pelo (inglés)</span>
        <p className={t.hint}>
          Siempre se inyecta en cada prompt. Incluye <strong className="text-inherit">bare head / no hat</strong> para evitar gorros.
        </p>
        <textarea
          className={`${t.input} min-h-[48px]`}
          value={settings.protagonist_wardrobe_en}
          onChange={(e) => setSettings((s) => ({ ...s, protagonist_wardrobe_en: e.target.value }))}
        />
      </label>

      <div className={t.cardViolet}>
        <label className="block">
          <span className={`${t.label} ${theme === "dark" ? "text-violet-200" : "text-violet-950"}`}>
            Reglas de pose y acción (inglés)
          </span>
          <p className={`mt-1 text-[10px] ${theme === "dark" ? "text-violet-300/90" : "text-violet-900"}`}>
            Visual Planner + cola Gemini. Si está vacío, el servidor usa su texto por defecto (visible abajo en «Reglas del motor»).
          </p>
          <textarea
            className={`${t.input} mt-2 min-h-[120px] font-mono text-[10px] ${theme === "dark" ? "text-violet-100" : "text-violet-950"}`}
            value={settings.protagonist_action_rules_en}
            onChange={(e) => setSettings((s) => ({ ...s, protagonist_action_rules_en: e.target.value }))}
          />
        </label>

        <div className={`mt-2 border-t pt-2 ${theme === "dark" ? "border-violet-500/30" : "border-violet-200/80"}`}>
          <p className={`text-[10px] font-semibold ${theme === "dark" ? "text-violet-200" : "text-violet-900"}`}>
            Validaciones automáticas al planificar
          </p>
          <ul className={`mt-1 list-inside list-disc space-y-0.5 text-[10px] ${theme === "dark" ? "text-violet-300/90" : "text-violet-900"}`}>
            {VISUAL_PLANNER_VALIDATIONS_ES.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {plannerConfig?.has_action_pose_rules === false ? (
            <p className="mt-1 text-[10px] text-amber-800">
              Aviso: no hay reglas guardadas — el backend usará el texto por defecto hasta que guardes.
            </p>
          ) : null}
        </div>
      </div>

      <div className={t.cardEmerald}>
        <label className="block">
          <span className={`${t.label} ${theme === "dark" ? "text-emerald-200" : "text-emerald-950"}`}>
            Expresiones faciales (catálogo · inglés)
          </span>
          <p className={`mt-1 text-[10px] ${theme === "dark" ? "text-emerald-300/90" : "text-emerald-900"}`}>
            Una línea por expresión: <code className={t.code}>clave: descripción visual</code>.
            El planner y las <strong>miniaturas en Metadata</strong> infieren la expresión según el tono de cada idea.
          </p>
          <textarea
            className={`${t.input} mt-2 min-h-[140px] font-mono text-[10px] ${theme === "dark" ? "text-emerald-100" : "text-emerald-950"}`}
            value={settings.protagonist_expressions_en}
            onChange={(e) => setSettings((s) => ({ ...s, protagonist_expressions_en: e.target.value }))}
          />
        </label>
        <ul className={`mt-2 list-inside list-disc space-y-0.5 border-t pt-2 text-[10px] ${theme === "dark" ? "border-emerald-500/30 text-emerald-300/90" : "border-emerald-200/80 text-emerald-900"}`}>
          {VISUAL_EXPRESSION_PLANNER_ES.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>

      <label className="block">
        <span className={t.label}>Evitar (Avoid)</span>
        <p className={t.hint}>
          Tu lista manual. El motor añade más términos en «Suplemento Avoid automático» (editable abajo).
        </p>
        <textarea
          className={`${t.input} min-h-[48px]`}
          value={settings.avoid_en}
          onChange={(e) => setSettings((s) => ({ ...s, avoid_en: e.target.value }))}
        />
      </label>

      <div className={t.cardSky}>
        <p className={`text-[10px] font-semibold uppercase tracking-wide ${t.label}`}>
          Reglas del motor (antes ocultas en el backend)
        </p>
        <p className={`mt-1 text-[10px] ${t.hint}`}>
          Lo gris dentro del cuadro es solo una pista, <strong className="text-inherit">no es contenido guardado</strong>.
          Si el cuadro está vacío y la etiqueta dice «Vacío → builtin», el servidor sí aplica reglas (ver texto desplegable debajo de cada campo).
        </p>

        <MotorRuleField
          label="Reglas extra del Visual Planner (inglés)"
          hint="Solo cuenta lo que escribes tú en el cuadro. Vacío = reglas largas del servidor (desplegable)."
          value={settings.planner_extra_rules_en}
          builtinText={rulesPreview?.builtin_defaults.planner_extra_rules_en}
          theme={theme}
          t={t}
          minH="min-h-[72px]"
          onChange={(v) => setSettings((s) => ({ ...s, planner_extra_rules_en: v }))}
        />

        <MotorRuleField
          label="Prefijo continuidad Gemini — imágenes 2+ (inglés)"
          hint="Prefijo antes de cada escena a partir de la 2.ª imagen en la cola Gemini."
          value={settings.gemini_continuity_prefix_en}
          builtinText={rulesPreview?.builtin_defaults.gemini_continuity_prefix_en}
          theme={theme}
          t={t}
          minH="min-h-[48px]"
          onChange={(v) => setSettings((s) => ({ ...s, gemini_continuity_prefix_en: v }))}
        />

        <MotorRuleField
          label="Suplemento Avoid automático (inglés)"
          hint="Se concatena a tu campo «Evitar» (gorros, posturas prohibidas, etc.)."
          value={settings.auto_avoid_supplement_en}
          builtinText={rulesPreview?.builtin_defaults.auto_avoid_supplement_en}
          theme={theme}
          t={t}
          minH="min-h-[40px]"
          onChange={(v) => setSettings((s) => ({ ...s, auto_avoid_supplement_en: v }))}
        />
      </div>

      {rulesPreview ? (
        <details className={t.cardSky} open>
          <summary className={`cursor-pointer text-[11px] font-semibold ${t.label}`}>
            Resumen: qué aplicará el servidor en esta sesión
          </summary>
          <div className={`mt-2 space-y-2 text-[10px] ${theme === "dark" ? "text-slate-300" : "text-sky-900"}`}>
            {Object.keys(rulesPreview.fallback_used_when_empty).length > 0 ? (
              <p className="text-amber-700 dark:text-amber-300">
                Estos campos del formulario principal están vacíos y el servidor usará su default interno:
                {" "}
                {Object.keys(rulesPreview.fallback_used_when_empty).join(", ")}.
              </p>
            ) : (
              <p>Todos los campos principales del formulario tienen texto guardado.</p>
            )}
            <p>
              <strong>Avoid efectivo (lo que va al prompt):</strong> {rulesPreview.effective_avoid_en}
            </p>
            <ul className="list-inside list-disc">
              {rulesPreview.scene_validation_rules_es.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </details>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <label className={`text-[11px] ${t.label}`}>
          <span className="font-medium">Ratio</span>
          <select
            className={t.select}
            value={settings.aspect_ratio}
            onChange={(e) => setSettings((s) => ({ ...s, aspect_ratio: e.target.value }))}
          >
            <option value="16:9">16:9</option>
            <option value="9:16">9:16</option>
            <option value="1:1">1:1</option>
          </select>
        </label>
        <label className={`text-[11px] ${t.label}`}>
          <span className="font-medium">Resolución</span>
          <select
            className={t.select}
            value={settings.output_spec}
            onChange={(e) => setSettings((s) => ({ ...s, output_spec: e.target.value }))}
          >
            <option value="2K output">2K</option>
            <option value="4K output">4K</option>
            <option value="1K output">1K</option>
          </select>
        </label>
      </div>

      <div className="flex items-center gap-3">
        <Btn
          type="button"
          className={t.btn}
          disabled={saving}
          onClick={() => void save()}
        >
          {saving ? "Guardando…" : isDraftNew ? "Crear estilo guardado" : "Guardar estilo"}
        </Btn>
        {saved ? <span className={t.saved}>Guardado</span> : null}
      </div>
    </div>
  );
}
