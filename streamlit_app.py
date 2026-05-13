#!/usr/bin/env python3
"""
Interfaz Streamlit opcional para probar el pipeline Videomaker.

Lanzar desde la raíz del proyecto (venv activado, PYTHONPATH al backend):

    PYTHONPATH=apps/backend streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "apps" / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import streamlit as st
from dotenv import load_dotenv

from videomaker.core import config
from videomaker.core.models import Locale, ScriptBlueprint
from videomaker.llm.script_gen import dry_run_prompt, generate_script


def _parse_locale(s: str) -> Locale:
    s = (s or "es").lower().strip()
    if s in ("es", "spa", "spanish"):
        return Locale.ES
    return Locale.EN


def _safe_work_dir(rel: str) -> Path:
    root = config.PROJECT_ROOT.resolve()
    p = (root / rel.strip().lstrip("/")).resolve()
    if not p.is_relative_to(root):
        raise ValueError("La carpeta de trabajo debe estar dentro del proyecto.")
    return p


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="Videomaker", layout="wide", initial_sidebar_state="expanded")
    st.title("Videomaker")
    st.caption("Guion → voz → montaje draft (MoviePy). Las API keys van en `.env`.")

    with st.sidebar:
        st.subheader("Carpeta de trabajo")
        wd = st.text_input(
            "Ruta relativa al proyecto",
            value=st.session_state.get("work_rel", "output/ui_session"),
            help="Aquí se guardarán guion.txt, narracion.wav, draft.mp4",
        )
        st.session_state["work_rel"] = wd
        try:
            work = _safe_work_dir(wd)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        work.mkdir(parents=True, exist_ok=True)
        st.code(str(work), language="text")
        st.divider()
        st.markdown("**APIs (.env)**")
        st.write("- `ANTHROPIC_API_KEY` — guion (si usas Claude en este flujo)")
        st.divider()
        st.markdown("**Lanzamiento**")
        st.code(
            "cd "
            + str(config.PROJECT_ROOT)
            + "\nexport PYTHONPATH=apps/backend\nsource .venv/bin/activate\nstreamlit run streamlit_app.py",
            language="bash",
        )

    tab_prompt, tab_tts, tab_pipe = st.tabs(
        ["1 · Prompt y guion", "2 · Voz (prueba)", "3 · Narración y vídeo"]
    )

    with tab_prompt:
        st.subheader("Palabras clave y prompt maestro")
        kw = st.text_input("Palabras clave (separadas por comas)", "motivación, hábitos, enfoque")
        ctx = st.text_area("Contexto extra (opcional)", height=100)
        col1, col2 = st.columns(2)
        with col1:
            lang = st.selectbox("Idioma", ["es", "en"], index=0)
        with col2:
            minutes = st.slider("Minutos objetivo", 4.0, 12.0, 8.0, 0.5)
        keywords = [k.strip() for k in kw.split(",") if k.strip()]
        bp = ScriptBlueprint(
            keywords=keywords,
            extra_context=ctx,
            locale=_parse_locale(lang),
            target_minutes=float(minutes),
        )
        if st.button("Ver prompt (sin gastar API)", type="secondary"):
            st.session_state["prompt_preview"] = dry_run_prompt(bp)
        if "prompt_preview" in st.session_state:
            st.text_area("Vista previa SYSTEM + USER", st.session_state["prompt_preview"], height=320)

        st.divider()
        st.subheader("Generar guion con Claude")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.warning("Falta `ANTHROPIC_API_KEY` en `.env` para generar el guion aquí.")
        st.session_state.setdefault("script_editor", "")
        if st.button("Generar guion", type="primary", disabled=not os.environ.get("ANTHROPIC_API_KEY")):
            try:
                with st.spinner("Llamando a Claude…"):
                    st.session_state["script_editor"] = generate_script(bp)
            except Exception as e:
                msg = str(e)
                if "credit balance is too low" in msg.lower():
                    st.error(
                        "Anthropic devolvió 400 por **saldo insuficiente**. "
                        "Puedes seguir usando la app sin generar guion (usa 'Ver prompt' o sube `guion.txt`)."
                    )
                else:
                    st.exception(e)
        st.text_area("Guion (editable)", height=400, key="script_editor")
        if st.button("Guardar como guion.txt en la carpeta de trabajo"):
            p = work / "guion.txt"
            p.write_text(st.session_state["script_editor"], encoding="utf-8")
            st.success(f"Guardado: {p}")

    with tab_tts:
        st.subheader("Síntesis de una frase (Coqui / XTTS)")
        st.caption("Requiere `pip install TTS torch` en el venv. La primera ejecución descarga modelos.")
        from videomaker.tts.voice_gen import VOICE_PRESETS, get_voice_preset, synthesize_with_coqui

        preset = st.selectbox("Preset de voz", sorted(VOICE_PRESETS.keys()), index=0)
        phrase = st.text_area("Texto a narrar", "Hola, esto es una prueba de voz desde la interfaz web.", height=80)
        if st.button("Generar WAV", type="primary"):
            out = work / "tts_ui_demo.wav"
            try:
                with st.spinner("Sintetizando… (puede tardar la primera vez)"):
                    synthesize_with_coqui(phrase, get_voice_preset(preset), out)
                st.audio(str(out), format="audio/wav")
                st.success(str(out.resolve()))
            except Exception as e:
                st.exception(e)

    with tab_pipe:
        st.subheader("Narración completa y montaje draft")
        guion_path = work / "guion.txt"
        if guion_path.is_file():
            st.success(f"Hay guion: `{guion_path.name}`")
        else:
            st.info("Pasa por la pestaña 1 y guarda `guion.txt`, o súbelo abajo.")

        up = st.file_uploader("Subir guion.txt (opcional)", type=["txt"])
        if up is not None:
            work.mkdir(parents=True, exist_ok=True)
            (work / "guion.txt").write_bytes(up.getvalue())
            st.success("Guion subido a la carpeta de trabajo.")
            st.rerun()

        from videomaker.tts.voice_gen import VOICE_PRESETS, get_voice_preset
        from videomaker.audio.narration import build_narration_wav
        from videomaker.web.io_util import finalize_new_narration

        preset_n = st.selectbox("Preset narración", sorted(VOICE_PRESETS.keys()), index=0, key="preset_narr")
        max_seg = st.number_input("Máx. fragmentos TTS (vacío = todos)", min_value=0, value=0, help="0 = sin límite; usa 2–3 para pruebas rápidas.")
        max_chars = st.number_input("Máx. caracteres por fragmento", min_value=200, value=900, step=50)

        if st.button("1 · Sintetizar narracion.wav", type="primary"):
            if not guion_path.is_file():
                st.error("No existe guion.txt en la carpeta de trabajo.")
            else:
                text = guion_path.read_text(encoding="utf-8")
                profile = get_voice_preset(preset_n)
                lim = int(max_seg) if max_seg else None
                try:
                    with st.spinner("TTS por fragmentos + concatenación…"):
                        wav, dur = build_narration_wav(
                            text,
                            profile,
                            work,
                            max_chars_per_segment=int(max_chars),
                            max_segments=lim,
                        )
                        finalize_new_narration(work)
                    st.session_state["last_wav"] = str(wav)
                    st.audio(str(wav), format="audio/wav")
                    st.success(f"{wav} — {dur:.1f} s ({dur / 60:.2f} min)")
                except Exception as e:
                    st.exception(e)

        st.divider()
        st.subheader("2 · Montar draft.mp4")
        st.caption("Usa `narracion.wav`, imágenes en `pipeline/images/` si existen, o fondo sólido.")
        no_music = st.checkbox("Sin música automática de musica_libre/", value=False)
        do_subs = st.checkbox("Generar subtítulos (Whisper + ffmpeg) después del MP4", value=False)
        whisper_lang = st.text_input("Idioma Whisper (opcional)", placeholder="es o en — vacío = autodetectar")
        if st.button("Renderizar vídeo", type="primary"):
            from videomaker.video.render import render_draft_video
            from videomaker.video.subtitles_whisper import segments_to_srt, transcribe_for_subtitles
            from videomaker.video.subtitles_ffmpeg import burn_subtitles_srt

            narr = work / "narracion.wav"
            stock_dir = work / "stock"
            out = work / "draft.mp4"
            if not narr.is_file():
                st.error("Falta narracion.wav — ejecuta el paso 1.")
            else:
                try:
                    with st.spinner("MoviePy está renderizando (puede tardar varios minutos)…"):
                        render_draft_video(
                            narr,
                            stock_dir,
                            out,
                            work_dir=work,
                            music_path=None,
                            pick_music_from_project=not no_music,
                            render_no_music=bool(no_music),
                        )
                    st.success(str(out.resolve()))
                    st.video(str(out))
                except Exception as e:
                    st.exception(e)
                    st.stop()
                if do_subs:
                    try:
                        with st.spinner("Whisper + ffmpeg…"):
                            wl = whisper_lang.strip() or None
                            segs = transcribe_for_subtitles(narr, language=wl)
                            srt_path = work / f"{out.stem}.srt"
                            srt_path.write_text(segments_to_srt(segs), encoding="utf-8")
                            out_subs = out.with_name(out.stem + "_subs.mp4")
                            burn_subtitles_srt(out, srt_path, out_subs)
                        st.success(f"Subtítulos: {out_subs.resolve()}")
                        st.video(str(out_subs))
                    except Exception as e:
                        st.exception(e)


if __name__ == "__main__":
    main()
