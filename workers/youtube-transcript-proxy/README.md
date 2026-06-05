# YouTube transcript proxy (Cloudflare Worker)

Obtiene subtítulos **públicos** de YouTube (`timedtext`) desde la red de Cloudflare, sin usar tu IP local.

```
Videomaker backend → Worker (Cloudflare) → YouTube
```

**¿Error `entitlements.not_available`?** → Sigue **[SETUP_CLOUDFLARE.md](./SETUP_CLOUDFLARE.md)** paso a paso (activar `workers.dev` + primer deploy en la web).

## Despliegue en Cloudflare

```bash
cd workers/youtube-transcript-proxy
npm install
npx wrangler login
npx wrangler deploy
```

### Error `entitlements.not_available [10007]`

Significa que **tu cuenta no tiene Workers activado** (o la API de Cloudflare falló). Prueba en este orden:

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages** → **Create** → Worker “Hello World” y **Deploy** desde la web.
   - Si aquí también falla, la cuenta no tiene el producto (email sin verificar, cuenta limitada, etc.).
2. Verifica el correo de la cuenta Cloudflare.
3. `npx wrangler logout` y `npx wrangler login` (elige la cuenta correcta si tienes varias).
4. `npx wrangler whoami` — debe listar tu cuenta sin error.
5. Si sigue igual: soporte Cloudflare o cuenta nueva gratuita.

### Alternativa sin Cloudflare (recomendado si ves `entitlements.not_available`)

Misma API HTTP. El backend no distingue CF Worker vs Python.

#### Opción A — Render (gratis, ~5 min)

1. [render.com](https://render.com) → **New +** → **Web Service**.
2. Conecta el repo GitHub de Videomaker (o sube solo la carpeta).
3. Configuración:
   - **Root Directory**: `workers/youtube-transcript-proxy`
   - **Runtime**: Python 3
   - **Start Command**: `python proxy_server.py`
   - **Health Check Path**: `/health`
4. Variables de entorno:
   - `TRANSCRIPT_PROXY_SECRET` = una clave larga (o usa *Generate*).
5. **Create Web Service** → copia la URL pública, ej. `https://videomaker-transcript-proxy.onrender.com`.

En `.env` del proyecto:

```env
YOUTUBE_TRANSCRIPT_WORKER_URL=https://videomaker-transcript-proxy.onrender.com
YOUTUBE_TRANSCRIPT_WORKER_SECRET=la-misma-clave-de-TRANSCRIPT_PROXY_SECRET
VIDEOMAKER_TRANSCRIPT_PROVIDER=auto
```

Prueba:

```bash
curl "https://TU-APP.onrender.com/health"
curl -H "Authorization: Bearer TU-SECRET" \
  "https://TU-APP.onrender.com/transcript?video_id=dQw4w9WgXcQ&lang=en"
```

#### Opción B — Local (solo pruebas; **no** evita IpBlocked)

```bash
bash scripts/run_transcript_proxy.sh
# en .env: YOUTUBE_TRANSCRIPT_WORKER_URL=http://127.0.0.1:8787
```

#### Opción C — Docker

```bash
cd workers/youtube-transcript-proxy
docker build -t transcript-proxy .
docker run -p 8787:8787 -e TRANSCRIPT_PROXY_SECRET=clave transcript-proxy
```

Copia la URL que imprime Wrangler (ej. `https://videomaker-youtube-transcript.<tu-cuenta>.workers.dev`).

### Secreto (recomendado)

```bash
npx wrangler secret put TRANSCRIPT_PROXY_SECRET
# introduce una contraseña larga aleatoria
```

En el `.env` del proyecto:

```env
YOUTUBE_TRANSCRIPT_WORKER_URL=https://videomaker-youtube-transcript.<cuenta>.workers.dev
YOUTUBE_TRANSCRIPT_WORKER_SECRET=la-misma-clave
VIDEOMAKER_TRANSCRIPT_PROVIDER=auto
```

## Endpoints

| Ruta | Descripción |
|------|-------------|
| `GET /health` | Estado del worker |
| `GET /transcript?video_id=VIDEO_ID&lang=es` | Texto del subtítulo |

Autenticación opcional: `Authorization: Bearer <TRANSCRIPT_PROXY_SECRET>` o header `X-Transcript-Proxy-Secret`.

## Desarrollo local

```bash
npm run dev
# prueba: curl "http://localhost:8787/transcript?video_id=dQw4w9WgXcQ&lang=en"
```

## Límites

- Plan gratuito de Workers: ~100k peticiones/día (suficiente para lotes moderados).
- No sustituye OAuth de `captions.download` para vídeos propios; en modo `auto` el backend intenta Data API primero y usa el worker cuando hay 403 o en fallback.
