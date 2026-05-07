#!/usr/bin/env python3
"""
Entrada provisional del proyecto: inspección de prompts y plan de stock
sin necesidad de GPU. La UI (Streamlit/Qt/etc.) reutilizará estos mismos módulos.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from videomaker.keyword_planner import plan_stock_keywords
from videomaker.models import Locale, ScriptBlueprint
from videomaker.script_gen import dry_run_prompt, generate_script
from videomaker.voice_gen import VOICE_PRESETS


def _parse_locale(s: str) -> Locale:
    s = s.lower().strip()
    if s in ("es", "spa", "spanish"):
        return Locale.ES
    return Locale.EN


def cmd_prompt(args: argparse.Namespace) -> None:
    bp = ScriptBlueprint(
        keywords=args.keywords,
        extra_context=args.context or "",
        locale=_parse_locale(args.lang),
        target_minutes=args.minutes,
    )
    text = dry_run_prompt(bp)
    print(text)


def cmd_script(args: argparse.Namespace) -> None:
    bp = ScriptBlueprint(
        keywords=args.keywords,
        extra_context=args.context or "",
        locale=_parse_locale(args.lang),
        target_minutes=args.minutes,
    )
    out = generate_script(bp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    print(f"Guion escrito en {out_path}")


def cmd_stock_plan(args: argparse.Namespace) -> None:
    script = Path(args.script_file).read_text(encoding="utf-8")
    lang = "es" if _parse_locale(args.lang) == Locale.ES else "en"
    plan = plan_stock_keywords(script, audio_duration_s=args.audio_seconds, lang_hint=lang)
    for q in plan[: args.limit]:
        print(f"{q.start_audio_s:6.1f}-{q.end_audio_s:6.1f}s  {q.query}")


def cmd_tts(args: argparse.Namespace) -> None:
    from videomaker.voice_gen import get_voice_preset, synthesize_with_coqui

    profile = get_voice_preset(args.preset)
    if args.speaker_wav:
        profile = replace(
            profile,
            speaker_wav=Path(args.speaker_wav),
            auto_clone_from_samples=False,
        )
    if args.builtin_speaker:
        profile = replace(
            profile,
            xtts_builtin_speaker=args.builtin_speaker,
            speaker_wav=None,
            auto_clone_from_samples=False,
        )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    synthesize_with_coqui(
        args.text,
        profile,
        out,
        split_sentences=False if args.no_split_sentences else None,
    )
    print(f"Audio escrito en {out.resolve()}")


def cmd_speak_script(args: argparse.Namespace) -> None:
    from videomaker.narration import build_narration_wav
    from videomaker.voice_gen import get_voice_preset

    script = Path(args.script_file).read_text(encoding="utf-8")
    profile = get_voice_preset(args.preset)
    if args.speaker_wav:
        profile = replace(
            profile,
            speaker_wav=Path(args.speaker_wav),
            auto_clone_from_samples=False,
        )
    if args.builtin_speaker:
        profile = replace(
            profile,
            xtts_builtin_speaker=args.builtin_speaker,
            speaker_wav=None,
            auto_clone_from_samples=False,
        )
    work = Path(args.work_dir)
    wav, dur = build_narration_wav(
        script,
        profile,
        work,
        max_chars_per_segment=args.max_chars,
        max_segments=args.max_segments,
    )
    print(f"Narración: {wav.resolve()}")
    print(f"Duración: {dur:.1f} s ({dur / 60:.2f} min)")


def cmd_render_draft(args: argparse.Namespace) -> None:
    from videomaker.render import render_draft_video
    from videomaker.subtitles_ffmpeg import burn_subtitles_srt
    from videomaker.subtitles_whisper import segments_to_srt, transcribe_for_subtitles

    work = Path(args.work_dir)
    narration = Path(args.narration) if args.narration else work / "narracion.wav"
    stock_dir = Path(args.stock_dir) if args.stock_dir else work / "stock"
    out = Path(args.out) if args.out else work / "draft.mp4"
    music = Path(args.music) if args.music else None
    fs = (args.width, args.height)

    render_draft_video(
        narration,
        stock_dir,
        out,
        music_path=music,
        pick_music_from_project=not args.no_music_auto,
        frame_size=fs,
    )
    print(f"Vídeo generado: {out.resolve()}")

    if args.subs:
        segs = transcribe_for_subtitles(
            narration,
            language=args.whisper_lang,
        )
        srt_path = work / f"{out.stem}.srt"
        srt_path.write_text(segments_to_srt(segs), encoding="utf-8")
        out_subs = out.with_name(out.stem + "_subs.mp4")
        burn_subtitles_srt(out, srt_path, out_subs)
        print(f"SRT: {srt_path.resolve()}")
        print(f"Vídeo con subtítulos: {out_subs.resolve()}")


def cmd_stock_fetch(args: argparse.Namespace) -> None:
    from videomaker.audio_concat import wav_duration_seconds
    from videomaker.stock_download import download_stock_for_queries
    from videomaker.stock_pexels import PexelsClient

    script = Path(args.script_file).read_text(encoding="utf-8")
    lang = "es" if _parse_locale(args.lang) == Locale.ES else "en"
    audio_s = None
    if args.audio:
        audio_s = wav_duration_seconds(Path(args.audio))
    plan = plan_stock_keywords(script, audio_duration_s=audio_s, lang_hint=lang)
    client = PexelsClient()
    out_dir = Path(args.out_dir)
    paths = download_stock_for_queries(
        client, plan, out_dir, max_downloads=args.max_clips
    )
    print(f"Descargados {len(paths)} clips en {out_dir.resolve()}")
    for p in paths:
        print(f"  {p.name}")


def cmd_tts_speakers(_args: argparse.Namespace) -> None:
    from videomaker.voice_gen import list_xtts_builtin_speakers

    names = list_xtts_builtin_speakers()
    if not names:
        print(
            "No se pudo leer la lista de voces (¿TTS instalado?). "
            "Prueba: tts --model_name tts_models/multilingual/multi-dataset/xtts_v2 --list_speaker_idx"
        )
        return
    for n in sorted(names):
        print(n)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Videomaker — utilidades de pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p0 = sub.add_parser("prompt", help="Muestra el prompt maestro sin llamar a la API")
    p0.add_argument("keywords", nargs="*", help="Palabras clave del tema")
    p0.add_argument("--context", "-c", default="", help="Descripción adicional")
    p0.add_argument("--lang", default="es", help="es | en")
    p0.add_argument("--minutes", type=float, default=10.0)
    p0.set_defaults(func=cmd_prompt)

    p1 = sub.add_parser("script", help="Genera guion con Claude (requiere ANTHROPIC_API_KEY)")
    p1.add_argument("keywords", nargs="*", help="Palabras clave del tema")
    p1.add_argument("--context", "-c", default="", help="Descripción adicional")
    p1.add_argument("--lang", default="es", help="es | en")
    p1.add_argument("--minutes", type=float, default=10.0)
    p1.add_argument("--out", default="output/guion.txt")
    p1.set_defaults(func=cmd_script)

    p2 = sub.add_parser("stock-plan", help="Lista queries de stock a partir del guion")
    p2.add_argument("script_file", type=Path)
    p2.add_argument("--audio-seconds", type=float, default=None, help="Duración real del audio")
    p2.add_argument("--lang", default="es")
    p2.add_argument("--limit", type=int, default=40)
    p2.set_defaults(func=cmd_stock_plan)

    p3 = sub.add_parser(
        "tts",
        help="Prueba Coqui / ⓍTTS v2 en local (requiere pip install TTS + torch)",
    )
    p3.add_argument(
        "--preset",
        default="xtts_v2_es",
        choices=sorted(VOICE_PRESETS.keys()),
    )
    p3.add_argument("--text", required=True, help="Frase a sintetizar")
    p3.add_argument("--out", default="output/tts_demo.wav")
    p3.add_argument(
        "--speaker-wav",
        default=None,
        help="WAV de referencia para clonar (anula búsqueda en voice_samples/)",
    )
    p3.add_argument(
        "--builtin-speaker",
        default=None,
        help="Nombre de voz integrada XTTS (anula clonación por archivo)",
    )
    p3.add_argument(
        "--no-split-sentences",
        action="store_true",
        help="Un solo pase (más VRAM; útil en textos cortos)",
    )
    p3.set_defaults(func=cmd_tts)

    p4 = sub.add_parser(
        "tts-speakers",
        help="Lista voces integradas del modelo XTTS v2 (tras instalar TTS)",
    )
    p4.set_defaults(func=cmd_tts_speakers)

    p5 = sub.add_parser(
        "speak-script",
        help="Lee un guion .txt, sintetiza por trozos y genera narracion.wav",
    )
    p5.add_argument("script_file", type=Path)
    p5.add_argument(
        "--work-dir",
        default="output/narracion",
        help="Carpeta para tts_chunks/ y narracion.wav",
    )
    p5.add_argument(
        "--preset",
        default="xtts_v2_es",
        choices=sorted(VOICE_PRESETS.keys()),
    )
    p5.add_argument("--speaker-wav", default=None)
    p5.add_argument("--builtin-speaker", default=None)
    p5.add_argument("--max-chars", type=int, default=900)
    p5.add_argument(
        "--max-segments",
        type=int,
        default=None,
        help="Solo los N primeros fragmentos (prueba rápida)",
    )
    p5.set_defaults(func=cmd_speak_script)

    p6 = sub.add_parser(
        "stock-fetch",
        help="Plan de keywords + descarga de vídeos Pexels (PEXELS_API_KEY)",
    )
    p6.add_argument("script_file", type=Path)
    p6.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="WAV de narración para ajustar ventanas al tiempo real",
    )
    p6.add_argument("--out-dir", default="output/stock", type=Path)
    p6.add_argument("--lang", default="es")
    p6.add_argument("--max-clips", type=int, default=35)
    p6.set_defaults(func=cmd_stock_fetch)

    p7 = sub.add_parser(
        "render-draft",
        help="Monta narracion.wav + carpeta stock/ → MP4 (música opcional desde musica_libre/)",
    )
    p7.add_argument(
        "--work-dir",
        default="output/narracion",
        help="Carpeta por defecto con narracion.wav y stock/",
    )
    p7.add_argument("--narration", default=None, help="Ruta al WAV (por defecto work-dir/narracion.wav)")
    p7.add_argument("--stock-dir", default=None, help="Carpeta con .mp4 (por defecto work-dir/stock)")
    p7.add_argument("--out", default=None, help="Salida .mp4 (por defecto work-dir/draft.mp4)")
    p7.add_argument("--music", default=None, help="Pista de música concreta (si no, aleatoria de musica_libre)")
    p7.add_argument(
        "--no-music-auto",
        action="store_true",
        help="No elegir música automática de musica_libre/",
    )
    p7.add_argument("--width", type=int, default=1920)
    p7.add_argument("--height", type=int, default=1080)
    p7.add_argument(
        "--subs",
        action="store_true",
        help="Tras el MP4, transcribe con Whisper y genera *_subs.mp4 con ffmpeg",
    )
    p7.add_argument(
        "--whisper-lang",
        default=None,
        help="Código idioma para Whisper (es, en). Omitir = autodetectar",
    )
    p7.set_defaults(func=cmd_render_draft)

    args = parser.parse_args()
    if args.command == "script" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Define ANTHROPIC_API_KEY en tu entorno o en .env antes de generar el guion."
        )
    if args.command == "stock-fetch" and not os.environ.get("PEXELS_API_KEY"):
        raise SystemExit("Define PEXELS_API_KEY en .env para descargar stock.")
    args.func(args)


if __name__ == "__main__":
    main()
