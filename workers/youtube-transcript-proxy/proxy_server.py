#!/usr/bin/env python3
"""
Proxy local de subtítulos (misma API que el Worker CF).

Uso:
  python proxy_server.py
  curl "http://127.0.0.1:8787/transcript?video_id=dQw4w9WgXcQ&lang=en"

En .env (solo desarrollo; sigue saliendo desde tu IP):
  YOUTUBE_TRANSCRIPT_WORKER_URL=http://127.0.0.1:8787

Para evitar IpBlocked despliega este script en Render/Railway/Fly (gratis)
y pon esa URL pública en YOUTUBE_TRANSCRIPT_WORKER_URL.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT") or os.environ.get("TRANSCRIPT_PROXY_PORT") or "8787")
SECRET = (
    os.environ.get("TRANSCRIPT_PROXY_SECRET")
    or os.environ.get("YOUTUBE_TRANSCRIPT_WORKER_SECRET")
    or ""
).strip()

WATCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en-US,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}


def _fetch(url: str, *, headers: dict[str, str] | None = None) -> str:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_json(html: str, marker: str) -> dict | None:
    idx = html.find(marker)
    if idx < 0:
        return None
    start = html.find("{", idx + len(marker))
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _caption_tracks(player: dict) -> list:
    caps = player.get("captions") or {}
    for key in ("playerCaptionsRenderer", "playerCaptionsTracklistRenderer"):
        tracks = (caps.get(key) or {}).get("captionTracks")
        if isinstance(tracks, list):
            return tracks
    return []


def _lang_prefs(lang: str) -> list[str]:
    code = (lang or "es").strip().lower()
    prefs = [code]
    for x in ("es", "en"):
        if x not in prefs:
            prefs.append(x)
    return prefs


def _pick_track(tracks: list, prefs: list[str]) -> dict | None:
    if not tracks:
        return None

    def by_lang(code: str):
        for t in tracks:
            lc = (t.get("languageCode") or "").lower()
            if lc == code or lc.startswith(f"{code}-"):
                return t
        return None

    for p in prefs:
        t = by_lang(p)
        if t and t.get("baseUrl"):
            return t
    for t in tracks:
        if t.get("kind") != "asr" and t.get("baseUrl"):
            return t
    for t in tracks:
        if t.get("baseUrl"):
            return t
    return None


def _parse_json3(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    lines = []
    for ev in data.get("events") or []:
        if not isinstance(ev, dict):
            continue
        segs = ev.get("segs")
        if not isinstance(segs, list):
            continue
        line = "".join((s.get("utf8") or "").replace("\n", " ") for s in segs if isinstance(s, dict)).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _parse_xml(raw: str) -> str:
    texts = []
    for m in re.finditer(r"<text[^>]*>([\s\S]*?)</text>", raw, re.I):
        t = m.group(1)
        for a, b in (
            ("&amp;", "&"),
            ("&lt;", "<"),
            ("&gt;", ">"),
            ("&quot;", '"'),
            ("&#39;", "'"),
        ):
            t = t.replace(a, b)
        t = t.replace("\n", " ").strip()
        if t:
            texts.append(t)
    return "\n".join(texts).strip()


def _timedtext_url(base: str, fmt: str) -> str:
    u = urllib.parse.urlparse(base)
    q = urllib.parse.parse_qs(u.query)
    if fmt and "fmt" not in q:
        q["fmt"] = [fmt]
    new_q = urllib.parse.urlencode({k: v[0] for k, v in q.items()})
    return urllib.parse.urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, u.fragment))


def _fetch_timedtext(track: dict) -> tuple[str, str]:
    base = track.get("baseUrl") or ""
    if not base:
        return "", "track_sin_baseUrl"
    for fmt in ("json3", "vtt", ""):
        url = _timedtext_url(base, fmt) if fmt else base
        try:
            raw = _fetch(url, headers={"User-Agent": WATCH_HEADERS["User-Agent"], "Accept": "*/*"})
        except urllib.error.HTTPError as e:
            continue
        except urllib.error.URLError:
            continue
        if not raw.strip():
            continue
        if fmt == "json3" or raw.strip().startswith("{"):
            text = _parse_json3(raw)
            if text:
                return text, fmt
        if "WEBVTT" in raw:
            lines = [
                ln.strip()
                for ln in raw.split("\n")
                if ln.strip()
                and not ln.startswith("WEBVTT")
                and not re.match(r"^\d+$", ln.strip())
                and "-->" not in ln
            ]
            text = "\n".join(lines).strip()
            if text:
                return text, "vtt"
        text = _parse_xml(raw)
        if text:
            return text, "xml"
    return "", "timedtext_vacio"


def fetch_transcript(video_id: str, lang: str) -> dict:
    watch = f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}"
    try:
        html = _fetch(watch, headers=WATCH_HEADERS)
    except urllib.error.HTTPError as e:
        return {"error": "watch_failed", "message": f"watch HTTP {e.code}", "http_status": e.code}
    except urllib.error.URLError as e:
        return {"error": "watch_failed", "message": str(e.reason)}

    player = _extract_json(html, "ytInitialPlayerResponse")
    if not player:
        return {"error": "no_player", "message": "No ytInitialPlayerResponse"}
    tracks = _caption_tracks(player)
    if not tracks:
        return {"error": "no_captions", "message": "Sin pistas públicas"}
    track = _pick_track(tracks, _lang_prefs(lang))
    if not track:
        return {"error": "no_track", "message": "Sin pista de idioma"}
    text, fmt = _fetch_timedtext(track)
    if not text:
        return {"error": "empty_transcript", "message": "timedtext vacío", "lang": track.get("languageCode")}
    return {
        "video_id": video_id,
        "lang": track.get("languageCode") or lang,
        "text": text,
        "source": "timedtext",
        "fmt": fmt,
    }


class Handler(BaseHTTPRequestHandler):
    def _auth_ok(self) -> bool:
        if not SECRET:
            return True
        auth = self.headers.get("Authorization", "")
        bearer = auth[7:].strip() if auth.startswith("Bearer ") else ""
        header = (self.headers.get("X-Transcript-Proxy-Secret") or "").strip()
        return bearer == SECRET or header == SECRET

    def _json(self, body: dict, status: int = 200) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if not self._auth_ok():
            self._json({"error": "unauthorized"}, 401)
            return
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if path in ("/", "/health"):
            self._json({"ok": True, "service": "youtube-transcript-proxy-python"})
            return
        if path == "/transcript":
            vid = (qs.get("video_id") or [""])[0].strip()
            lang = (qs.get("lang") or ["es"])[0].strip()
            if not vid or not re.match(r"^[a-zA-Z0-9_-]{6,20}$", vid):
                self._json({"error": "invalid_video_id"}, 400)
                return
            try:
                result = fetch_transcript(vid, lang)
            except Exception as e:
                self._json({"error": "server_error", "message": str(e)}, 500)
                return
            if result.get("error"):
                self._json(result, 422)
                return
            self._json(result)
            return
        self._json({"error": "not_found"}, 404)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> None:
    # 0.0.0.0 en PaaS (Render/Railway); 127.0.0.1 en local por defecto
    host = os.environ.get("TRANSCRIPT_PROXY_HOST") or (
        "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    )
    print(f"Transcript proxy en http://{host}:{PORT}  (SECRET={'sí' if SECRET else 'no'})")
    HTTPServer((host, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
