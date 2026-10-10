"""
test_templates.py

QUÉ:
    Tests unitarios para la integración de plantillas, assets y mitigación de tracking en cliente:
    - Integridad de copia de ba_track.js (static vs assets).
    - Render y directivas de mitigación en _cookie_consent.html.
    - Ejecución de la suite de navegador baTrack (Node.js).
POR QUÉ:
    Garantizar que no existan desfasajes entre el código estático activo y la referencia de la skill,
    y verificar que el banner respete la mitigación activa y la idempotencia.
CÓMO:
    Django Template rendering, validación de hashes/bytes de archivos y subprocess runner de Node.
"""

import os
import subprocess
from pathlib import Path
import pytest
from django.template.loader import render_to_string
from django.conf import settings


def test_ba_track_assets_synced_byte_by_byte():
    """
    Verifica que el archivo estático activo static/js/ba_track.js coincida exactamente
    con el archivo espejo en la skill .agents/skills/tracking-specialist/assets/ba_track.js.
    """
    static_file = Path(settings.BASE_DIR) / "static" / "js" / "ba_track.js"
    asset_file = Path(settings.BASE_DIR) / ".agents" / "skills" / "tracking-specialist" / "assets" / "ba_track.js"

    assert static_file.exists(), "static/js/ba_track.js debe existir"
    assert asset_file.exists(), ".agents/.../assets/ba_track.js debe existir"

    static_content = static_file.read_bytes()
    asset_content = asset_file.read_bytes()

    assert static_content == asset_content, (
        "El asset de referencia debe ser idéntico byte por byte a static/js/ba_track.js"
    )


def test_cookie_consent_banner_render_and_contracts():
    """
    Verifica que el template _cookie_consent.html renderice correctamente y cumpla
    con las directivas de consentimiento estricto, emisión síncrona y cookie espejo.
    """
    rendered = render_to_string("includes/partials/_cookie_consent.html", {})

    # 1. Debe incluir emisión inmediata al guardar preferencias
    assert "window.dispatchEvent(new CustomEvent('ba:consent-applied'" in rendered, (
        "El banner debe emitir el evento ba:consent-applied inmediatamente"
    )

    # 2. Debe incluir actualización en caliente de Google Consent Mode si gtag existe
    assert "gtag('consent', 'update'" in rendered, (
        "El banner debe actualizar gtag('consent', 'update') sincrónicamente en _save()"
    )

    # 3. Debe escribir la cookie ba_consent con formato a=1|d=1 y SameSite=Lax
    assert 'ba_consent=a="' in rendered and '|d="' in rendered, (
        "La cookie espejo ba_consent debe generarse con formato estricto a=1|d=1"
    )
    assert "SameSite=Lax" in rendered, "La cookie espejo debe definir SameSite=Lax"


def test_ba_track_browser_node_suite_passes():
    """
    Ejecuta la suite de verificación del comportamiento del navegador en Node.js
    (test_ba_track.js) y asegura que todos los asertos de cliente pasen con código 0.
    """
    test_script = Path(settings.BASE_DIR) / "tracking" / "tests" / "test_ba_track.js"
    assert test_script.exists(), "tracking/tests/test_ba_track.js debe existir"

    result = subprocess.run(
        ["node", str(test_script)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, (
        f"La suite de pruebas Node de baTrack falló con código {result.returncode}.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
