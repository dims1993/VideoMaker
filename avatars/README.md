# Avatars

Carpeta central para todo el material visual de los avatares del canal.

## Estructura

```
avatars/
└── <avatar_id>/               ← mismo ID que en avatars.json
    ├── references/            ← imágenes de referencia que subes tú
    │   └── (*.png / *.jpg)
    └── generated/             ← imágenes generadas con IA para este avatar
        └── (*.png / *.jpg / *.webp)
```

Cada `<avatar_id>` coincide exactamente con el campo `id` en `avatars.json`
(e.g. `nerd_boy_v1`, o el hex que el backend asigna a avatares nuevos).

## Avatares actuales

| ID | Nombre |
|----|--------|
| `nerd_boy_v1` | Nerd Boy (canal por defecto) |

## Flujo de trabajo

1. **Sube imágenes de referencia** a `<avatar_id>/references/`  
   — fotos, bocetos o ejemplos del estilo que quieres para el personaje.

2. **Construye el prompt base** en `avatars.json` (`description` + `style_notes`)  
   usando las referencias como guía visual.

3. **Genera variantes** (expresiones, situaciones) con el Avatar Prompt Writer  
   desde la UI → los prompts quedan en `pipeline/image_prompts.json` por sesión.

4. **Guarda las imágenes generadas** que apruebas en `<avatar_id>/generated/`  
   para usar como referencia en generaciones futuras o en el vídeo final.

## Añadir un avatar nuevo

1. Crea el avatar desde la UI (sección **Avatars** en la pipeline).
2. Crea la carpeta manualmente:
   ```
   avatars/<nuevo_id>/references/
   avatars/<nuevo_id>/generated/
   ```
3. Sube las imágenes de referencia y ajusta `description` + `style_notes` en la UI.
