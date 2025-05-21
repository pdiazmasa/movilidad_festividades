# streamlit_app.py – versión con descargas automáticas (completa)
"""
Aplicación Streamlit para visualizar la movilidad interprovincial en fiestas y
ofrecer la descarga inmediata de cualquier archivo generado mediante un botón.

Modos disponibles
=================
1. **Mapa interactivo de un día** → Folium incrustado.
2. **Mapa interactivo mensual**   → HTML + descarga.
3. **Mapa mensual con imágenes**  → HTML + descarga.
4. **Comparar dos provincias**    → HTML + descarga.
5. **Mapa relativo**              → Folium incrustado + descarga.
6. **GIF animado del mes**        → GIF + descarga.

Dependencias mínimas (requirements.txt)
---------------------------------------
streamlit
streamlit-folium>=0.18
pandas
openpyxl
folium
geopandas
shapely
jinja2
"""

import sys
import subprocess
import mimetypes
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium
from funciones_app import (
    graficaTransportesDia,
    exportar_mapa_interactivo_mes,
    exportar_mapa_con_imagenes_mes,
    comparar_mapas,
    mapa_transportes_relativo,
    exportar_mapa_gif,
)

# ─────────────────────────────────────────────────────
# Soporte PyInstaller (ignorado en Streamlit Cloud)
# ─────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    tmp = Path(sys.argv[0]).parent
    subprocess.Popen([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(tmp / "streamlit_app.py"),
        "--server.port", "8501",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "true",
    ])
    sys.exit(0)

# ─────────────────────────────────────────────────────
# Configuración de página
# ─────────────────────────────────────────────────────
st.set_page_config(page_title="Panel de Movilidad", page_icon="🧭")
st.title("🗺️ GENERADOR DE MAPAS 🗺️")

# ─────────────────────────────────────────────────────
# Estado inicial de sesión
# ─────────────────────────────────────────────────────
for key in ("mapa_dia", "params_dia"):
    st.session_state.setdefault(key, None)

# ─────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────

def show_progress(gen):
    bar = st.progress(0)
    res = None
    for chunk in gen:
        if isinstance(chunk, int):
            bar.progress(chunk)
        else:
            res = chunk
    bar.empty()
    return res


def embed_folium(m, w=760, h=560):
    components.html(m.get_root().render(), width=w, height=h, scrolling=False)


def offer_download(path: Path, label: str):
    if not path or not path.exists():
        return
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "application/octet-stream"
    st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime)

# Cache simple para mapa diario
@st.cache_resource(show_spinner=False)
def cache_mapa(c, d, m_, s, z):
    gen = graficaTransportesDia(c, d, m_, s, z)
    for chunk in gen:
        if not isinstance(chunk, int):
            return chunk

# ─────────────────────────────────────────────────────
# Menú lateral
# ─────────────────────────────────────────────────────
menu = [
    "🗓️ Mapa interactivo de un día",
    "📅 Mapa Interactivo de un mes",
    "🖼️ Mapa de un mes con imágenes",
    "🆚 Comparar dos mapas",
    "📊 Mapa relativo de un día",
    "🎞️ GIF de un mes",
]
op = st.sidebar.radio("Elige función", menu)

# ─────────────────────────────────────────────────────
# 1) Mapa interactivo de un día
# ─────────────────────────────────────────────────────
if op == menu[0]:
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)
    if st.button("Generar mapa"):
        st.session_state["params_dia"] = (c, d, m_, s, z)
        st.session_state["mapa_dia"] = cache_mapa(c, d, m_, s, z)
    if st.session_state["mapa_dia"] is not None:
        embed_folium(st.session_state["mapa_dia"])

# ─────────────────────────────────────────────────────
# 2) HTML mensual interactivo
# ─────────────────────────────────────────────────────
elif op == menu[1]:
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar HTML"):
        ruta = show_progress(exportar_mapa_interactivo_mes(c, m_, s))
        st.success("HTML generado ✔")
        offer_download(Path(ruta), "Descargar HTML")

# ─────────────────────────────────────────────────────
# 3) HTML mensual con imágenes
# ─────────────────────────────────────────────────────
elif op == menu[2]:
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 7)
    if st.button("Generar HTML imágenes"):
        ruta = show_progress(exportar_mapa_con_imagenes_mes(c, m_, s, z))
        st.success("HTML generado ✔")
        offer_download(Path(ruta), "Descargar HTML")

# ─────────────────────────────────────────────────────
# 4) Comparar dos mapas
# ─────────────────────────────────────────────────────
elif op == menu[3]:
    c1 = st.text_input("Provincia A")
    m1 = st.number_input("Mes A", 1, 12, 1, key="m1")
    s1 = st.number_input("Sensibilidad A", 1, 10, 3, key="s1")
    c2 = st.text_input("Provincia B")
    m2 = st.number_input("Mes B", 1, 12, 1, key="m2")
    s2 = st.number_input("Sensibilidad B", 1, 10, 3, key="s2")
    z = st.number_input("Zoom", 4, 10, 6)
    if st.button("Generar comparativa"):
        ruta = show_progress(comparar_mapas(c1, m1, s1, c2, m2, s2, z))
        st.success("HTML comparativo ✔")
        offer_download(Path(ruta), "Descargar HTML")

# ─────────────────────────────────────────────────────
# 5) Mapa relativo por mil habitantes
# ─────────────────────────────────────────────────────
elif op == menu[4]:
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar mapa relativo"):
        ruta = show_progress(mapa_transportes_relativo(c, d, m_, s, open_browser=False))
        ruta = Path(ruta)
        if ruta.exists():
            components.html(ruta.read_text(encoding="utf-8"), width=760, height=560, scrolling=False)
            offer_download(ruta, "Descargar HTML")

# ─────────────────────────────────────────────────────
# 6) GIF animado del mes
# ─────────────────────────────────────────────────────
elif op == menu[5]:
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)
    secs = st.number_input("Segundos por frame", 0.05, 2.0, 0.1, step=0.05)
    if st st.button("Generar GIF"):
        ruta = show_progress(exportar_mapa_gif(c, m_, s, z, secs, open_browser=False))
        ruta = Path(ruta)
        if ruta.exists():
            st.success("GIF generado ✔")
            offer_download(ruta, "Descargar GIF")


    secs = st.number_input("Segundos por frame", 0.05, 2.0, 0.1, step=0.05)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_gif(c, m_, s, z, secs, open_browser=True))
        st.success(f"GIF generado: {ruta}")

