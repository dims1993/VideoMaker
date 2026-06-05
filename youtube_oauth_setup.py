#!/usr/bin/env python3
"""
Genera YOUTUBE_OAUTH_REFRESH_TOKEN para captions.list / captions.download.

Requisitos en Google Cloud Console:
  1. Proyecto con «YouTube Data API v3» habilitada
  2. Credenciales OAuth 2.0 → Tipo «Aplicación de escritorio»
  3. En la credencial, URI de redirección autorizada: http://127.0.0.1:8765/oauth2callback
  4. Pantalla de consentimiento OAuth → si el estado es «En pruebas» (Testing), añade tu
     cuenta de Google en «Usuarios de prueba». Si no, verás Error 403: access_denied.
     Enlace: APIs y servicios → Pantalla de consentimiento de OAuth → Usuarios de prueba

Uso (desde la raíz del repo):

  source .venv/bin/activate
  python youtube_oauth_setup.py

Variables en .env (client id/secret antes de ejecutar; refresh token después):

  YOUTUBE_OAUTH_CLIENT_ID=
  YOUTUBE_OAUTH_CLIENT_SECRET=
  YOUTUBE_OAUTH_REFRESH_TOKEN=   ← lo imprime este script

YOUTUBE_API_KEY es aparte (metadatos); no sustituye a OAuth para subtítulos.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parent
SCOPES = "https://www.googleapis.com/auth/youtube.force-ssl"
REDIRECT_URI = "http://127.0.0.1:8765/oauth2callback"


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for key, val in dotenv_values(env_path).items():
        if val and not str(os.environ.get(key, "")).strip():
            os.environ[key] = val


class _Handler(BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/oauth2callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = parse_qs(parsed.query)
        _Handler.code = (qs.get("code") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Autorizacion OK</h2>"
            b"<p>Puedes cerrar esta ventana y volver a la terminal.</p></body></html>"
        )

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    os.chdir(REPO_ROOT)
    _load_dotenv()
    client_id = (os.environ.get("YOUTUBE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        print(
            "Faltan YOUTUBE_OAUTH_CLIENT_ID y/o YOUTUBE_OAUTH_CLIENT_SECRET en .env\n"
            f"Archivo esperado: {REPO_ROOT / '.env'}"
        )
        return 1

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={requests.utils.quote(client_id)}"
        f"&redirect_uri={requests.utils.quote(REDIRECT_URI)}"
        "&response_type=code"
        f"&scope={requests.utils.quote(SCOPES)}"
        "&access_type=offline"
        "&prompt=consent"
    )
    print("Abre el navegador para autorizar acceso a YouTube (captions)...")
    print(
        "\nSi Google muestra «solo testers aprobados» / Error 403 access_denied:\n"
        "  Google Cloud → APIs y servicios → Pantalla de consentimiento de OAuth\n"
        "  → sección «Usuarios de prueba» → + AÑADIR USUARIOS → tu Gmail\n"
        "  Vuelve a ejecutar este script.\n"
    )
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    server = HTTPServer(("127.0.0.1", 8765), _Handler)
    print("Esperando callback en http://127.0.0.1:8765/oauth2callback ...")
    server.handle_request()

    code = _Handler.code
    if not code:
        print(
            "No se recibió código de autorización.\n"
            "Si en el navegador viste 403 access_denied, añade tu Gmail como "
            "«Usuario de prueba» en la Pantalla de consentimiento OAuth (modo Testing)."
        )
        return 1

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"Error al intercambiar código ({r.status_code}): {r.text}")
        return 1
    data = r.json() or {}
    refresh = data.get("refresh_token")
    if not refresh:
        print(
            "No hay refresh_token. Usa prompt=consent y revoca el acceso previo en "
            "https://myaccount.google.com/permissions si hace falta."
        )
        print(data)
        return 1

    print("\n--- Añade a tu .env (raíz del repo) ---\n")
    print(f"YOUTUBE_OAUTH_REFRESH_TOKEN={refresh}")
    print("\nReinicia dev.sh. YOUTUBE_API_KEY sigue siendo necesaria para metadatos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
