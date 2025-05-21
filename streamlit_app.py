# streamlit_app.py

import sys
import subprocess
import uuid
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada para el EXE de PyInstaller:
if getattr(sys, "frozen", False):
    temp_dir = Path(sys.argv[0]).parent
    script   = temp_dir / "streamlit_app.py"
    subprocess.Popen([
        sys.executable,
        "-m", "streamlit", "run", str(script),
        "--server.port", "8501",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "true",
    ])
    sys.exit(0)
# ─────────────────────────────────────────────────────────────────────────────

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

# ── Configuración general ───────────────────────────────────────────────────
st.set_page_config(page_title="Panel de Movilidad", page_icon="🧭")
st.title("🗺️ GENERADOR DE MAPAS 🗺️")

# ── Estado inicial ──────────────────────────────────────────────────────────
if "params_dia" not in st.session_state:
    st.session_state["params_dia"] = None  # (c, d, m, s, z)
if "mapa_dia" not in st.session_state:
    st.session_state["mapa_dia"] = None    # objeto folium.Map

# ── Selector de funcionalidad ───────────────────────────────────────────────
op = st.sidebar.radio(
    "Elige función",
    [
        "🗓️ Mapa interactivo de un día",
        "📅 Mapa Interactivo de un mes",
        "🖼️ Mapa de un mes con imágenes",
        "🆚 Comparar dos mapas",
        "📊 Mapa relativo de un día",
        "🎞️ GIF de un mes",
    ],
)

titles = {
    "🗓️ Mapa interactivo de un día": "Transporte Día",
    "📅 Mapa Interactivo de un mes": "Mapa Interactivo Mensual",
    "🖼️ Mapa de un mes con imágenes": "Mapa Mensual con Imágenes",
    "🆚 Comparar dos mapas": "Comparación de Ciudades",
    "📊 Mapa relativo de un día": "Transporte Relativo por Habitante",
    "🎞️ GIF de un mes": "GIF Animado del Mes",
}

descs = {
    "🗓️ Mapa interactivo de un día": "Colorea las provincias según volumen de viajes en un día concreto.",
    "📅 Mapa Interactivo de un mes": "Genera un HTML con todos los días y un slider para navegar entre ellos.",
    "🖼️ Mapa de un mes con imágenes": "Toma capturas PNG diarias e incrústalas en un HTML con slider.",
    "🆚 Comparar dos mapas": "Muestra lado a lado dos provincias para un rango de días común.",
    "📊 Mapa relativo de un día": "Colorea según viajes por mil habitantes, resaltando la provincia destino.",
    "🎞️ GIF de un mes": "Crea un GIF animado con la evolución diaria del mes.",
}

st.header(titles[op])
st.markdown(descs[op])

# ── Utilidad: barra de progreso única ───────────────────────────────────────

def show_progress(gen):
    barra = st.progress(0)
    res = None
    for paso in gen:
        if isinstance(paso, int):
            barra.progress(paso)
        else:
            res = paso
    barra.empty()
    return res

# ── Función para construir mapa (cacheada) ──────────────────────────────────
@st.cache_resource(show_spinner=False)
def build_map(c, d, m, s, z):
    gen = graficaTransportesDia(c, d, m, s, z)
    mapa = None
    for chunk in gen:
        if not isinstance(chunk, int):
            mapa = chunk
    return mapa

# ── Modo 1: Mapa interactivo de un día ──────────────────────────────────────
if op == "🗓️ Mapa interactivo de un día":
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)

    if st.button("Generar"):
        st.session_state["params_dia"] = (c, d, m_, s, z)
        # Generamos con progreso y guardamos resultado
        st.session_state["mapa_dia"] = show_progress(graficaTransportesDia(c, d, m_, s, z))

    # Si ya hay parámetros guardados pero no mapa (por ejemplo en primer rerun),
    # construimos el mapa rápidamente vía cache.
    if st.session_state["params_dia"] and st.session_state["mapa_dia"] is None:
        st.session_state["mapa_dia"] = build_map(*st.session_state["params_dia"])

    # Mostrar mapa si existe
    if st.session_state["mapa_dia"] is not None:
        unique_key = f"mapa_dia_{uuid.uuid4()}"  # fuerza recarga completa del iframe
        st_folium(st.session_state["mapa_dia"], width=750, height=550, key=unique_key)

# ── Modo 2: HTML mensual interactivo ────────────────────────────────────────
elif op == "📅 Mapa Interactivo de un mes":
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_interactivo_mes(c, m_, s))
        st.success(f"HTML generado: {ruta}")

# ── Modo 3: HTML mensual con imágenes ───────────────────────────────────────
elif op == "🖼️ Mapa de un mes con imágenes":
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 7)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_con_imagenes_mes(c, m_, s, z))
        st.success(f"HTML generado: {ruta}")

# ── Modo 4: Comparar dos mapas ──────────────────────────────────────────────
elif op == "🆚 Comparar dos mapas":
    c1 = st.text_input("Provincia A")
    m1 = st.number_input("Mes A", 1, 12, 1, key="m1")
    s1 = st.number_input("Sensibilidad A", 1, 10, 3, key="s1")
    c2 = st.text_input("Provincia B")
    m2 = st.number_input("Mes B", 1, 12, 1, key="m2")
    s2 = st.number_input("Sensibilidad B", 1, 10, 3, key="s2")
    z  = st.number_input("Zoom", 4, 10, 6)
    if st.button("Comparar"):
        ruta = show_progress(comparar_mapas(c1, m1, s1, c2, m2, s2, z))
        st.success(f"HTML comparativo generado: {ruta}")

# ── Modo 5: Mapa relativo por habitante ─────────────────────────────────────
elif op == "📊 Mapa relativo de un día":
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar"):
        ruta = show_progress(mapa_transportes_relativo(c, d, m_, s, open_browser=True))
        st.success(f"Mapa generado: {ruta}")

# ── Modo 6: GIF animado del mes ─────────────────────────────────────────────
elif op == "🎞️ GIF de un mes":
    c = st.text_input("Provincia")
    m_ = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)
    d = st.number_input("Segundos por frame", 0.05,

