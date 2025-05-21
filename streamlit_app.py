# streamlit_app.py

import sys
import subprocess
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada para el EXE de PyInstaller:
if getattr(sys, "frozen", False):
    # Encontramos el .py desempaquetado junto al exe
    temp_dir = Path(sys.argv[0]).parent
    script   = temp_dir / "streamlit_app.py"

    # Lanzamos un subproceso: Mapas.exe -m streamlit run streamlit_app.py
    subprocess.Popen([
        sys.executable,
        "-m", "streamlit", "run", str(script),
        "--server.port", "8501",            # opcional: fija el puerto
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "true"
    ])
    # Salimos inmediatamente del proceso padre
    sys.exit(0)
# ─────────────────────────────────────────────────────────────────────────────

# A partir de aquí, **solo** en desarrollo (python -m streamlit run streamlit_app.py)

import streamlit as st
from funciones_app import (
    graficaTransportesDia,
    exportar_mapa_interactivo_mes,
    exportar_mapa_con_imagenes_mes,
    comparar_mapas,
    mapa_transportes_relativo,
    exportar_mapa_gif,
)

# Configuración y UI de Streamlit
st.set_page_config(page_title="Panel de Movilidad", page_icon="🧭")
st.title("🗺️ GENERADOR DE MAPAS 🗺️")

op = st.sidebar.radio("Elige función", [
    "🗓️ Mapa interactivo de un día",
    "📅 Mapa Interactivo de un mes",
    "🖼️ Mapa de un mes con imágenes",
    "🆚 Comparar dos mapas",
    "📊 Mapa relativo de un día",
    "🎞️ GIF de un mes",
])

titles = {
    "🗓️ Mapa interactivo de un día":     "Transporte Día",
    "📅 Mapa Interactivo de un mes":     "Mapa Interactivo Mensual",
    "🖼️ Mapa de un mes con imágenes":    "Mapa Mensual con Imágenes",
    "🆚 Comparar dos mapas":             "Comparación de Ciudades",
    "📊 Mapa relativo de un día":        "Transporte Relativo por Habitante",
    "🎞️ GIF de un mes":                 "GIF Animado del Mes",
}
descs = {
    "🗓️ Mapa interactivo de un día":     "Colorea las provincias según volumen de viajes en un día concreto.",
    "📅 Mapa Interactivo de un mes":     "Genera un HTML con todos los días y un slider para navegar entre ellos.",
    "🖼️ Mapa de un mes con imágenes":    "Toma capturas PNG diarias e incrústalas en un HTML con slider.",
    "🆚 Comparar dos mapas":             "Muestra lado a lado dos provincias para un rango de días común.",
    "📊 Mapa relativo de un día":        "Colorea según viajes por mil habitantes, resaltando la provincia destino.",
    "🎞️ GIF de un mes":                 "Crea un GIF animado con la evolución diaria del mes.",
}

st.header(titles[op])
st.markdown(descs[op])

def show_progress(gen):
    prog = st.progress(0)
    ruta = None
    for x in gen:
        if isinstance(x, (int, float)):
            prog.progress(int(x))
        else:
            ruta = x
    prog.empty()
    return ruta

if op == "🗓️ Mapa interactivo de un día":
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)
    if st.button("Generar"):
        ruta = show_progress(graficaTransportesDia(c, d, m, s, z, open_browser=True))
        st.success(f"Mapa generado: {ruta}")

elif op == "📅 Mapa Interactivo de un mes":
    c = st.text_input("Provincia")
    m = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_interactivo_mes(c, m, s))
        st.success(f"HTML generado: {ruta}")

elif op == "🖼️ Mapa de un mes con imágenes":
    c = st.text_input("Provincia")
    m = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 7)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_con_imagenes_mes(c, m, s, z))
        st.success(f"HTML generado: {ruta}")

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

elif op == "📊 Mapa relativo de un día":
    c = st.text_input("Provincia")
    d = st.number_input("Día", 1, 31, 1)
    m = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    if st.button("Generar"):
        ruta = show_progress(mapa_transportes_relativo(c, d, m, s, open_browser=True))
        st.success(f"Mapa generado: {ruta}")

elif op == "🎞️ GIF de un mes":
    c = st.text_input("Provincia")
    m = st.number_input("Mes", 1, 12, 1)
    s = st.number_input("Sensibilidad color", 1, 10, 3)
    z = st.number_input("Zoom", 4, 10, 6)
    d = st.number_input("Segundos por frame", 0.05, 2.0, 0.1, step=0.05)
    if st.button("Generar"):
        ruta = show_progress(exportar_mapa_gif(c, m, s, z, d, open_browser=True))
        st.success(f"GIF generado: {ruta}")