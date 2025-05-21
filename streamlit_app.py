# streamlit_app.py – versión completa y corregida

import sys
import subprocess
import uuid
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

from funciones_app import (
    graficaTransportesDia,
    exportar_mapa_interactivo_mes,
    exportar_mapa_con_imagenes_mes,
    comparar_mapas,
    mapa_transportes_relativo,
    exportar_mapa_gif,
)

# ─────────────────────────────────────────────────────────────────────────────
# Soporte para PyInstaller (opcional)
if getattr(sys, "frozen", False):
    temp_dir = Path(sys.argv[0]).parent
    script = temp_dir / "streamlit_app.py"
    subprocess.Popen([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script),
        "--server.port",
        "8501",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "true",
    ])
    sys.exit(0)
# ─────────────────────────────────────────────────────────────────────────────

# ── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(page_title="Panel de Movilidad", page_icon="🧭")
st.title("🗺️ GENERADOR DE MAPAS 🗺️")

# ── Sesión: claves iniciales ────────────────────────────────────────────────
for key in ("mapa_dia", "params_dia"):
    st.session_state.setdefault(key, None)

# ── Selector lateral ────────────────────────────────────────────────────────
opciones = [
    "🗓️ Mapa interactivo de un día",
    "📅 Mapa Interactivo de un mes",
    "🖼️ Mapa de un mes con imágenes",
    "🆚 Comparar dos mapas",
    "📊 Mapa relativo de un día",
    "🎞️ GIF de un mes",
]

op = st.sidebar.radio("Elige función", opciones)

titles = {
    opciones[0]: "Transporte Día",
    opciones[1]: "Mapa Interactivo Mensual",
    opciones[2]: "Mapa Mensual con Imágenes",
    opciones[3]: "Comparación de Ciudades",
    opciones[4]: "Transporte Relativo por Habitante",
    opciones[5]: "GIF Animado del Mes",
}

descripciones = {
    opciones[0]: "Colorea las provincias según volumen de viajes en un día concreto.",
    opciones[1]: "Genera un HTML con todos los días y un slider para navegar entre ellos.",
    opciones[2]: "Toma capturas PNG diarias e incrústalas en un HTML con slider.",
    opciones[3]: "Muestra lado a lado dos provincias para un rango de días común.",
    opciones[4]: "Colorea según viajes por mil habitantes, resaltando la provincia destino.",
    opciones[5]: "Crea un GIF animado con la evolución diaria del mes.",
}

st.header(titles[op])
st.markdown(descripciones[op])

# ── Utilidad para progreso ─────────────────────────────────────────────────

def show_progress(generator):
    barra = st.progress(0)
    resultado = None
    for paso in generator:
        if isinstance(paso, int):
            barra.progress(paso)
        else:
            resultado = paso
    barra.empty()
    return resultado

# ── Cacheado rápido: reconstruye un mapa ya solicitado ──────────────────────
@st.cache_resource(show_spinner=False)
def build_map(c, d, m_, s, z):
    gen = graficaTransportesDia(c, d, m_, s, z)
    out = None
    for chunk in gen:
        if not isinstance(chunk, int):
            out = chunk
    return out

# ─────────────────────────────────────────────────────────────────────────────
# BLOQUES POR FUNCIÓN
# ─────────────────────────────────────────────────────────────────────────────

# 1) Mapa interactivo de un día ------------------------------------------------
if op == opciones[0]:
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)

    if st.button("Generar"):
        st.session_state["params_dia"] = (c, d, m_, s, z)
        st.session_state["mapa_dia"] = show_progress(graficaTransportesDia(c, d, m_, s, z))

    if st.session_state["params_dia"] and st.session_state["mapa_dia"] is None:
        st.session_state["mapa_dia"] = build_map(*st.session_state["params_dia"])

    if st.session_state["mapa_dia"] is not None:
        st_folium(
            st.session_state["mapa_dia"],
            width=760,
            height=560,
            key=f"mapa_dia_{uuid.uuid4()}",
        )

# 2) HTML mensual interactivo --------------------------------------------------
elif op == opciones[1]:
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_interactivo_mes(c, m_, s))
        st.success(f"HTML generado: {ruta}")

# 3) HTML mensual con imágenes -------------------------------------------------
elif op == opciones[2]:
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 7)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_con_imagenes_mes(c, m_, s, z))
        st.success(f"HTML generado: {ruta}")

# 4) Comparar dos mapas --------------------------------------------------------
elif op == opciones[3]:
    c1 = st.text_input("Provincia A")
    m1 = st.number_input("Mes A", 1, 12, 1, key="m1")
    s1 = st.number_input("Sensibilidad A", 1, 10, 3, key="s1")
    c2 = st.text_input("Provincia B")
    m2 = st.number_input("Mes B", 1, 12, 1, key="m2")
    s2 = st.number_input("Sensibilidad B", 1, 10, 3, key="s2")
    z = st.number_input("Zoom", 4, 10, 6)
    if st.button("Comparar"):
        ruta = show_progress(comparar_mapas(c1, m1, s1, c2, m2, s2, z))
        st.success(f"HTML comparativo generado: {ruta}")

# 5) Mapa relativo por habitante ----------------------------------------------
elif op == opciones[4]:
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar"):
        ruta = show_progress(mapa_transportes_relativo(c, d, m_, s, open_browser=True))
        st.success(f"Mapa generado: {ruta}")

# 6) GIF animado del mes -------------------------------------------------------
elif op == opciones[5]:
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)
    secs = st.number_input("Segundos por frame", 0.05, 2.0, 0.1, step=0.05)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_gif(c, m_, s, z, secs, open_browser=True))
        st.success(f"GIF generado: {ruta}")
