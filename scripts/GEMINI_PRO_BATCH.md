# Imágenes en lote con Google AI Pro (sin API prepay)

Tu suscripción **Google AI Pro** sirve para [gemini.google.com](https://gemini.google.com/app), no para la API de prepago de AI Studio que usa Videomaker con un clic.

Este script automatiza el flujo **Pro en el navegador** y guarda `001.png`, `002.png`, … en `pipeline/images/`.

## Modo recomendado: `assist`

Copia cada prompt al portapapeles, tú generas en Gemini (con Pro), y el script mueve el PNG desde Descargas.

```bash
cd /ruta/al/repo
source .venv/bin/activate

# Solo la escena 12 (prueba)
python scripts/gemini_pro_image_batch.py --work output/ui_session --orders 12

# Las 10 primeras pendientes
python scripts/gemini_pro_image_batch.py --work output/ui_session --limit 10

# Rango
python scripts/gemini_pro_image_batch.py --work output/ui_session --orders 1-20
```

En cada paso:

1. El prompt ya está en el portapapeles → pega en Gemini.
2. Genera la imagen (modo imagen / Nano Banana).
3. Descarga el PNG (queda en `~/Downloads`).
4. Pulsa **Enter** en la terminal → el script guarda `012.png` y actualiza el manifest.

Luego en Videomaker: **Images Generation → Recargar**.

## Modo `auto` (experimental)

Usa Chrome con tu sesión Google. Requiere `playwright`:

```bash
pip install playwright
playwright install chromium
```

1. Cierra Chrome.
2. Ábrelo con perfil dedicado y depuración remota:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.videomaker-chrome-profile"
```

3. Inicia sesión y abre Gemini.
4. En otra terminal:

```bash
python scripts/gemini_pro_image_batch.py --mode auto --work output/ui_session --limit 5
```

Si la UI de Google cambia, el modo auto puede fallar → usa `assist`.

## Límites Pro

- Pro da más imágenes **en la app**, no infinitas (p. ej. ~100/día en modelos Pro según la ayuda actual).
- No generes las 92 de golpe en un día; usa `--limit` y pausas.

## Requisitos

- `pipeline/images_generation.json` (desde Image Prompt Writer → Enviar a Images Generation).
- Cada fila debe tener `ai_prompt`.
