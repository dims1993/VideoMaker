# Activar Cloudflare Workers (checklist)

## Si el dashboard falla: `GET .../flags (503)`

Eso es la **API de Cloudflare caída o saturada** para tu cuenta, no un error de Videomaker.

1. Espera 15–30 min y recarga (modo incógnito, sin extensiones).
2. Estado global: https://www.cloudflarestatus.com/
3. Prueba otro navegador o red (móvil como hotspot).
4. Cierra sesión en Cloudflare y vuelve a entrar.
5. Si sigue 24 h → **Soporte Cloudflare** con:
   - Account ID: `d2a236dc9b1e2091014ce768456523d0`
   - Endpoint: `GET /accounts/.../flags` → HTTP 503
   - No puedes abrir Workers & Pages ni desplegar Workers

Mientras el 503 persista, **no podrás** activar Workers ni en web ni con Wrangler (mismo backend).

---

Si `wrangler deploy` falla con **`entitlements.not_available [10007]`**, casi siempre falta **activar Workers en la cuenta**, no hay bug en el código del repo.

## Paso 1 — Subdominio `workers.dev` (obligatorio la primera vez)

1. Abre: https://dash.cloudflare.com/?to=/:account/workers-and-pages  
2. Si te pide **elegir un subdominio** (ej. `davidmunoz.workers.dev`) → elígelo y confirma.  
3. Si ya tienes cuenta: en **Workers & Pages** → **Change** junto a *Your subdomain* y asegúrate de que existe un subdominio activo.

Sin este paso, muchas cuentas no pueden publicar scripts.

## Paso 2 — Primer Worker desde la web (no Wrangler)

1. En **Workers & Pages** → **Create** → **Create Worker**.  
2. Nombre: `hello-test` (solo letras y guiones).  
3. **Deploy** (código por defecto).  
4. Abre la URL `https://hello-test.TU-SUBDOMINIO.workers.dev` — debe responder.

- Si **esto falla** → la cuenta no tiene Workers; ver Paso 4.  
- Si **esto funciona** → la cuenta está bien; sigue con Paso 3.

## Paso 3 — Desplegar el proxy de transcripciones

```bash
cd workers/youtube-transcript-proxy
npm install
npx wrangler logout && npx wrangler login
npx wrangler whoami          # debe listar tu cuenta sin error
npx wrangler deploy
```

URL final:

`https://videomaker-youtube-transcript.TU-SUBDOMINIO.workers.dev`

Opcional (recomendado):

```bash
npx wrangler secret put TRANSCRIPT_PROXY_SECRET
```

## Paso 4 — Si sigue `entitlements.not_available`

| Causa habitual | Qué hacer |
|----------------|-----------|
| Email sin verificar | Verifica el correo de la cuenta Cloudflare |
| Cuenta solo DNS (sin Workers) | Misma cuenta en dashboard: debe existir menú **Workers & Pages** |
| Cuenta equivocada en Wrangler | `wrangler logout` → `login` → elige la cuenta correcta |
| Workers deshabilitado en org | Si es cuenta de empresa, pide a admin habilitar Workers |
| Límite / región / bug CF | Soporte: https://dash.cloudflare.com/?to=/:account/support — menciona `entitlements.not_available` al hacer PUT `/workers/scripts/` |

Prueba también en otro navegador o sin extensiones que bloqueen cookies de Cloudflare.

## Paso 5 — `.env` de Videomaker

```env
VIDEOMAKER_TRANSCRIPT_PROVIDER=auto
YOUTUBE_TRANSCRIPT_WORKER_URL=https://videomaker-youtube-transcript.TU-SUBDOMINIO.workers.dev
YOUTUBE_TRANSCRIPT_WORKER_SECRET=la-clave-de-wrangler-secret
```

Reinicia `bash scripts/dev.sh` y en Analyse: **Transcripts JSON → sesión**.

## Comprobar el Worker

```bash
curl "https://videomaker-youtube-transcript.TU-SUBDOMINIO.workers.dev/health"
curl -H "Authorization: Bearer TU-SECRET" \
  "https://videomaker-youtube-transcript.TU-SUBDOMINIO.workers.dev/transcript?video_id=dQw4w9WgXcQ&lang=en"
```

Debe devolver JSON con `"text": "..."`.
