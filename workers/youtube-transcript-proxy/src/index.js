/**
 * Proxy de subtítulos públicos de YouTube (timedtext) vía infraestructura Cloudflare.
 *
 * GET /health
 * GET /transcript?video_id=VIDEO_ID&lang=es
 * Header opcional: Authorization: Bearer <TRANSCRIPT_PROXY_SECRET>
 */

const WATCH_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  "Accept-Language": "es-ES,es;q=0.9,en-US,en;q=0.8",
  Accept: "text/html,application/xhtml+xml",
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function unauthorized() {
  return jsonResponse({ error: "unauthorized", message: "Token inválido o ausente" }, 401);
}

function checkAuth(request, env) {
  const secret = (env.TRANSCRIPT_PROXY_SECRET || "").trim();
  if (!secret) return true;
  const auth = request.headers.get("Authorization") || "";
  const bearer = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const header = (request.headers.get("X-Transcript-Proxy-Secret") || "").trim();
  return bearer === secret || header === secret;
}

function extractJsonObject(html, marker) {
  const idx = html.indexOf(marker);
  if (idx < 0) return null;
  const start = html.indexOf("{", idx + marker.length);
  if (start < 0) return null;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < html.length; i++) {
    const ch = html[i];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (ch === "\\") {
        escape = true;
        continue;
      }
      if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') {
      inString = true;
      continue;
    }
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        try {
          return JSON.parse(html.slice(start, i + 1));
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}

function captionTracksFromPlayer(player) {
  const tracks =
    player?.captions?.playerCaptionsRenderer?.captionTracks ||
    player?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
  return Array.isArray(tracks) ? tracks : [];
}

function langPrefs(lang) {
  const code = (lang || "es").trim().toLowerCase();
  const prefs = [code];
  for (const x of ["es", "en"]) {
    if (!prefs.includes(x)) prefs.push(x);
  }
  return prefs;
}

function pickTrack(tracks, prefs) {
  if (!tracks.length) return null;
  const byLang = (code) =>
    tracks.find((t) => (t.languageCode || "").toLowerCase() === code) ||
    tracks.find((t) => (t.languageCode || "").toLowerCase().startsWith(`${code}-`));
  for (const p of prefs) {
    const t = byLang(p);
    if (t?.baseUrl) return t;
  }
  const manual = tracks.find((t) => t.kind !== "asr" && t.baseUrl);
  if (manual) return manual;
  return tracks.find((t) => t.baseUrl) || null;
}

function parseJson3(raw) {
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return "";
  }
  const events = data?.events;
  if (!Array.isArray(events)) return "";
  const lines = [];
  for (const ev of events) {
    const segs = ev?.segs;
    if (!Array.isArray(segs)) continue;
    const line = segs
      .map((s) => (s?.utf8 || "").replace(/\n/g, " "))
      .join("")
      .trim();
    if (line) lines.push(line);
  }
  return lines.join("\n").trim();
}

function parseXmlCaptions(raw) {
  const texts = [];
  const re = /<text[^>]*>([\s\S]*?)<\/text>/gi;
  let m;
  while ((m = re.exec(raw)) !== null) {
    const t = m[1]
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/\n/g, " ")
      .trim();
    if (t) texts.push(t);
  }
  return texts.join("\n").trim();
}

function timedtextUrl(baseUrl, fmt) {
  const u = new URL(baseUrl);
  if (!u.searchParams.has("fmt")) u.searchParams.set("fmt", fmt);
  return u.toString();
}

async function fetchTimedtext(track) {
  const base = track.baseUrl;
  if (!base) return { text: "", error: "track_sin_baseUrl" };

  for (const fmt of ["json3", "vtt", ""]) {
    const url = fmt ? timedtextUrl(base, fmt) : base;
    const r = await fetch(url, {
      headers: {
        "User-Agent": WATCH_HEADERS["User-Agent"],
        Accept: "*/*",
      },
    });
    if (!r.ok) continue;
    const raw = await r.text();
    if (!raw.trim()) continue;
    if (fmt === "json3" || raw.trimStart().startsWith("{")) {
      const text = parseJson3(raw);
      if (text) return { text, fmt: "json3" };
    }
    if (fmt === "vtt" || raw.includes("WEBVTT")) {
      const lines = raw
        .split("\n")
        .filter((ln) => ln.trim() && !ln.startsWith("WEBVTT") && !/^\d+$/.test(ln.trim()) && !ln.includes("-->"))
        .map((ln) => ln.trim())
        .filter(Boolean);
      const text = lines.join("\n").trim();
      if (text) return { text, fmt: "vtt" };
    }
    const xmlText = parseXmlCaptions(raw);
    if (xmlText) return { text: xmlText, fmt: "xml" };
  }
  return { text: "", error: "timedtext_vacio" };
}

async function fetchTranscript(videoId, lang) {
  const watchUrl = `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`;
  const page = await fetch(watchUrl, { headers: WATCH_HEADERS });
  if (!page.ok) {
    return { error: "watch_failed", message: `watch HTTP ${page.status}`, http_status: page.status };
  }
  const html = await page.text();
  const player =
    extractJsonObject(html, "ytInitialPlayerResponse") ||
    extractJsonObject(html, "var ytInitialPlayerResponse");
  if (!player) {
    return { error: "no_player", message: "No se encontró ytInitialPlayerResponse en la página" };
  }
  const tracks = captionTracksFromPlayer(player);
  if (!tracks.length) {
    return { error: "no_captions", message: "El vídeo no tiene pistas de subtítulos públicas" };
  }
  const track = pickTrack(tracks, langPrefs(lang));
  if (!track) {
    return { error: "no_track", message: "No se pudo elegir pista de idioma" };
  }
  const { text, fmt, error } = await fetchTimedtext(track);
  if (!text) {
    return {
      error: error || "empty_transcript",
      message: "Pista encontrada pero timedtext vacío o bloqueado",
      lang: track.languageCode || null,
    };
  }
  return {
    video_id: videoId,
    lang: track.languageCode || lang,
    text,
    source: "timedtext",
    fmt: fmt || "unknown",
    kind: track.kind || null,
  };
}

export default {
  async fetch(request, env) {
    if (!checkAuth(request, env)) return unauthorized();

    const url = new URL(request.url);
    if (url.pathname === "/health" || url.pathname === "/") {
      return jsonResponse({ ok: true, service: "youtube-transcript-proxy" });
    }

    if (url.pathname === "/transcript") {
      const videoId = (url.searchParams.get("video_id") || "").trim();
      if (!videoId || !/^[a-zA-Z0-9_-]{6,20}$/.test(videoId)) {
        return jsonResponse(
          { error: "invalid_video_id", message: "Parámetro video_id inválido" },
          400,
        );
      }
      const lang = (url.searchParams.get("lang") || "es").trim();
      try {
        const result = await fetchTranscript(videoId, lang);
        if (result.error) {
          const status = result.error === "watch_failed" && result.http_status === 404 ? 404 : 422;
          return jsonResponse(result, status);
        }
        return jsonResponse(result);
      } catch (e) {
        return jsonResponse(
          { error: "worker_error", message: e?.message || String(e) },
          500,
        );
      }
    }

    return jsonResponse({ error: "not_found", message: "Usa GET /transcript?video_id=..." }, 404);
  },
};
