#!/usr/bin/env python
# coding: utf-8

# In[45]:


# In[46]:


# ── Standard library ──────────────────────────
import os
import sys
import time
import json
import base64
import webbrowser
from pathlib import Path
from tempfile import TemporaryDirectory
import unicodedata

# ── Third-party ───────────────────────────────
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster          # quítalo si no lo usas
from shapely.geometry import Point
from branca.element import Template, MacroElement
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import imageio.v2 as imageio
from jinja2 import Template                       # ya importada arriba; borra si no la necesitas duplicada

# ── Jupyter helpers (solo si trabajas en notebook) ──
from IPython.display import display, IFrame, clear_output
from ipywidgets import interact, widgets


# In[47]:


# ── Carpetas base y de datos/resultados ─────────────────────────
if getattr(sys, "frozen", False):                  # cuando esté empaquetado en .exe
    BASE_DIR = Path(sys.executable).resolve().parent
else:                                              # modo desarrollo o Jupyter
    try:
        BASE_DIR = Path(__file__).resolve().parent
    except NameError:                              # dentro de Notebook
        BASE_DIR = Path.cwd()

DATOS_DIR     = BASE_DIR / "datos"                 # Excel, geojson, etc.
RESULTADOS_DIR = BASE_DIR / "resultados"           # salidas generadas
RESULTADOS_DIR.mkdir(exist_ok=True)


# In[119]:


#!jupyter nbconvert --to script funciones_app.ipynb --output funciones_app


# In[51]:


def normalize_string(s):
    """
    Normaliza una cadena eliminando acentos y transformándola a minúsculas.
    """
    if pd.isna(s):
        return ""
    return unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('utf-8').lower().strip()


# In[53]:


def standardize_province_name(name):
    """
    Estandariza el nombre de una provincia usando un diccionario de equivalencias.
    Se pueden agregar o ajustar mapeos según las discrepancias encontradas.
    """
    norm_name = normalize_string(name)
    mapping = {
        "castellon": "castellon",
        "castellon/castello": "castellon",
        "castello": "castellon",  # Ejemplo de variante
        "alicante": "alicante",
        "alacant": "alicante",
        "alicante/alacant": "alicante",
        "araba": "alava",
        "araba/alava": "alava",
        "Araba/Álava": "alava",
        "Vitoria": "alava",
        "Álava": "alava",
        "\u00c1lava": "alava"
        # Puedes agregar aquí otros mapeos que sean necesarios
    }
    return mapping.get(norm_name, norm_name)


# In[55]:


def get_fill_color(volume, max_volume, sensibilidad):
    """
    Devuelve un código hexadecimal de color para el tono de azul, interpolando entre
    blanco (para volúmenes < 90) y azul oscuro (RGB 0,0,139) para el máximo de viajes.
    
    Antes de la interpolación se resta 90 a todos los volúmenes, de modo que:
      - Si volume < 90, se devuelve blanco puro.
      - Para volúmenes ≥ 90, se define el volumen efectivo = volume - 90, y el 
        máximo efectivo = max_volume - 90 (o 1 si max_volume <= 90), lo que reduce la
        diferencia entre 0 y 100.
    
    El parámetro 'sensibilidad' se utiliza para ajustar la curva de intensidad.
    """
    import pandas as pd
    
    # Comprobaciones iniciales.
    if volume is None or pd.isna(volume) or max_volume == 0:
        return "#ffffff"

    # Si volume es 0, lo tratamos como 1 (como se indicó anteriormente).
    if volume == 0:
        volume = 1
    
    # Si el volumen es menor que 90, se devuelve blanco puro.
    if volume < 90:
        return "#ffffff"
    
    # Calcular el volumen efectivo restando 90
    effective_volume = volume - 90
    effective_max = max_volume - 90 if max_volume > 90 else 1  # Evitar división por cero

    norm = effective_volume / effective_max
    intensity = norm ** (1.0 / sensibilidad)
    
    r = 255 - int(255 * intensity)
    g = 255 - int(255 * intensity)
    b = 255 - int(140 * intensity)  # Se mantiene 140 para obtener (255-140)=115 como base de azul oscuro
    return f"#{r:02x}{g:02x}{b:02x}"


# In[57]:


def detectar_campo_provincia(gdf, df_transport):
    """
    Intenta detectar cuál es el campo del GeoJSON que contiene los nombres de provincias.
    Primero se intenta comparar las columnas (excepto la de geometría) usando 
    la función standardize_province_name y comprobando coincidencias con los nombres
    estandarizados del df de transporte.
    Si no se encuentra ninguna coincidencia razonable, se usa un método "fallback":
    se consideran las columnas tipo objeto y se elige la de mayor cantidad de valores únicos.
    """
    # Obtenemos los nombres estandarizados del DataFrame de transporte
    transport_provinces = set(df_transport['prov_std'])
    
    candidate_fields = [col for col in gdf.columns if col.lower() != 'geometry']
    best_field = None
    best_matches = 0
    for field in candidate_fields:
        try:
            std_values = gdf[field].astype(str).apply(standardize_province_name)
        except Exception:
            continue
        count_matches = std_values.isin(transport_provinces).sum()
        if count_matches > best_matches:
            best_matches = count_matches
            best_field = field
    if best_field is None or best_matches == 0:
        # Fallback: elegir la columna de tipo objeto con mayor número de valores únicos
        object_fields = [col for col in gdf.columns if gdf[col].dtype == object]
        if object_fields:
            best_field = max(object_fields, key=lambda col: gdf[col].nunique())
            print("Fallback: se elige el campo", best_field, "con", gdf[best_field].nunique(), "valores únicos")
        else:
            print("No se detectó ningún campo de texto en el GeoJSON.")
            return None
    return best_field


# In[79]:


from pathlib import Path
from tempfile import TemporaryDirectory
import pandas as pd
import geopandas as gpd
import folium
from branca.element import Template, MacroElement
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import base64, json, time

def graficaTransportesDia(
        ciudad, dia, mes,
        sensibilidad_color: int = 3,
        zoom: int = 6,
        dpi_scale: float = 1.0,
        legend_side: str = "left",
):
    """
    Genera un folium.Map.
    Progreso 0–100; al final devuelve el mapa.
    dpi_scale escala los textos al capturar PNG.
    legend_side "left" o "right" para mostrar leyenda, otro valor omite leyenda.
    """
    mes = int(mes)
    transporte_file = DATOS_DIR / f"{ciudad.lower()}-{mes:02}.xlsx"
    georef_file     = DATOS_DIR / "georef-spain-provincia.geojson"

    yield 0
    if not georef_file.exists():
        raise FileNotFoundError(georef_file)
    if not transporte_file.exists():
        raise FileNotFoundError(transporte_file)
    yield 10

    gdf_provincias = gpd.read_file(georef_file)
    df_transporte  = pd.read_excel(transporte_file)
    yield 30

    df_dia = df_transporte[df_transporte["dia"] == dia]
    if df_dia.empty:
        raise ValueError(f"No hay datos para el día {dia}")
    df_agg = (
        df_dia.groupby("provincia origen", as_index=False)["viajes"].sum()
             .assign(prov_std=lambda d: d["provincia origen"]
                                        .apply(standardize_province_name))
    )
    best_field = detectar_campo_provincia(gdf_provincias, df_agg)
    if best_field is None:
        raise RuntimeError("No se detectó campo provincia válido")
    gdf_provincias["prov_std"] = gdf_provincias[best_field].apply(standardize_province_name)
    gdf_merged = gdf_provincias.merge(df_agg[["prov_std","viajes"]], on="prov_std", how="left")
    gdf_merged["viajes"] = gdf_merged["viajes"].fillna(0)
    yield 50

    max_viajes = gdf_merged["viajes"].max()
    centro = gdf_merged.to_crs("EPSG:3857").geometry.centroid.unary_union.centroid
    ctr_ll = gpd.GeoSeries([centro], crs="EPSG:3857")\
                 .to_crs("EPSG:4326").iloc[0]
    mapa = folium.Map(location=[ctr_ll.y, ctr_ll.x], zoom_start=zoom)
    yield 60

    # Overlay superior
    font_sup = round(14 * dpi_scale, 1)
    tpl_sup = f"""
    {{% macro html(this, kwargs) %}}
      <div style="
          position:fixed;
          top:10px;
          left:50%;
          transform:translate(-50%,0);
          z-index:9999;
          background:white;
          padding:8px 12px;
          border:2px solid grey;
          border-radius:4px;
          font-size:{font_sup}px;
          white-space:nowrap;
      ">
        Ciudad: {{{{this.ciudad}}}} | Mes: {{{{this.mes}}}} | Sensibilidad: {{{{this.sensibilidad}}}}
      </div>
    {{% endmacro %}}
    """
    sup = MacroElement()
    sup._template = Template(tpl_sup)
    sup.ciudad, sup.mes, sup.sensibilidad = ciudad, mes, sensibilidad_color
    mapa.get_root().add_child(sup)
    yield 70

    # GeoJSON
    estudio_std = standardize_province_name(ciudad)
    def style_function(feat):
        prov = standardize_province_name(feat["properties"].get(best_field, ""))
        if prov == estudio_std:
            fill = "#66f26a"
        else:
            fill = get_fill_color(feat["properties"].get("viajes",0),
                                  max_viajes, sensibilidad_color)
        return {"fillColor": fill, "color":"blue", "weight":1, "fillOpacity":1}
    folium.GeoJson(
        gdf_merged,
        style_function=style_function,
        tooltip=folium.features.GeoJsonTooltip(
            fields=[best_field, "viajes"],
            aliases=["Provincia", "Viajes"]
        )
    ).add_to(mapa)
    yield 90

    # Leyenda opcional
    if legend_side in ("left","right"):
        scale = dpi_scale * 0.8
        font_leg = round(13 * scale, 1)
        width_leg= int(260 * scale)
        side_css = "left:10px;" if legend_side=="left" else "right:10px;"
        legend_html = f"""
        <div style="
            position:fixed;
            bottom:10px;
            {side_css}
            width:{width_leg}px;
            background:white;
            border:2px solid grey;
            border-radius:4px;
            padding:10px;
            font-size:{font_leg}px;
            z-index:9999;
        ">
          <b>🗺️ Leyenda</b><br><br>
          <i style="background:#336699;width:12px;height:12px;display:inline-block;margin-right:5px;"></i>
            <b>Azul</b>: Provincias de origen<br>
          &nbsp;&nbsp;Más oscuro → más desplazamientos<br>
          <i style="background:#66f26a;width:12px;height:12px;display:inline-block;margin-right:5px;"></i>
            <b>Verde</b>: Provincia destino<br>
        </div>
        """
        mapa.get_root().html.add_child(folium.Element(legend_html))

    # Fin
    yield mapa


# In[97]:


def exportar_mapa_interactivo_mes(ciudad, mes, sensibilidad_color=3):
    """
    Devuelve un único HTML con un slider para navegar por los días del mes.
    Progreso: 0-100; al final, ruta del HTML combinando todos los mapas.

    La nueva versión usa graficaTransportesDia() sin open_browser
    y sin escribir mapas temporales en disco.
    """
    transporte_file = DATOS_DIR / f"{ciudad.lower()}-{int(mes):02}.xlsx"
    output_html     = RESULTADOS_DIR / f"interactivo_{ciudad}_{int(mes):02}.html"

    if not transporte_file.exists():
        raise FileNotFoundError(f"No se encontró {transporte_file}")

    # ---------- leer días disponibles ----------
    df = pd.read_excel(transporte_file)
    dias = sorted(df["dia"].dropna().unique())
    if not dias:
        raise ValueError("No hay días disponibles en el archivo")

    total = len(dias)
    yield 0      # inicio
    yield 5      # días leídos

    # ---------- generar mapas y recoger HTML ----------
    mapas_html = {}
    for idx, dia in enumerate(dias, start=1):
        # consumir el generador hasta obtener el mapa final
        gen = graficaTransportesDia(ciudad, dia, mes, sensibilidad_color, zoom=6)
        mapa = None
        for chunk in gen:
            if not isinstance(chunk, int):
                mapa = chunk

        # renderizar el folium.Map a string HTML
        mapas_html[dia] = mapa.get_root().render()

        yield 5 + int(idx / total * 85)   # progreso 5-90 %

    # ---------- ensamblar HTML con slider ----------
    min_d, max_d = dias[0], dias[-1]
    html_out = [f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Interactivo {ciudad} {mes}</title>
<style>
  body {{margin:0}} iframe.map {{position:absolute;top:0;left:0;width:100%;height:100vh;border:none;display:none}}
  #ctl {{position:fixed;top:20px;right:20px;background:#fff;padding:10px;border:2px solid grey;border-radius:8px;z-index:9999}}
</style>
</head><body>
<div id="ctl">
  Día: <input type="range" id="slider" min="{min_d}" max="{max_d}"
              value="{min_d}" oninput="chg(this.value)">
  <span id="lbl">{min_d}</span>
</div>
"""]

    for dia, html in mapas_html.items():
        esc = html.replace('"', "&quot;")
        html_out.append(f'<iframe id="d{dia}" class="map" srcdoc="{esc}"></iframe>')

    # script para el slider
    html_out.append(f"""
<script>
function chg(v) {{
  document.getElementById('lbl').textContent=v;
  document.querySelectorAll('iframe.map').forEach(f=>f.style.display='none');
  var fr=document.getElementById('d'+v); if(fr) fr.style.display='block';
}}
chg({min_d});
</script>
</body></html>""")

    output_html.write_text("".join(html_out), encoding="utf-8")
    yield 95  # ensamblado listo

    # devolver ruta y 100 %
    yield output_html


# In[101]:

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import base64, json, time
from tempfile import TemporaryDirectory

def exportar_mapa_con_imagenes_mes(ciudad, mes,
                                   sensibilidad_color: int = 3,
                                   zoom: int = 7):
    """
    Genera un HTML con una imagen PNG Hi-DPI por cada día disponible
    y un slider para alternar. Devuelve la ruta del HTML final.
    Progreso emitido: 0-100.
    """

    xls = DATOS_DIR / f"{ciudad.lower()}-{int(mes):02}.xlsx"
    out = RESULTADOS_DIR / f"imagenes_{ciudad}_{int(mes):02}.html"

    # ── 0 % : comprobaciones ────────────────────────────────────────────
    yield 0
    if not xls.exists():
        raise FileNotFoundError(xls)
    df   = pd.read_excel(xls)
    dias = sorted(df["dia"].dropna().unique())
    if not dias:
        raise ValueError("No hay días en el Excel")
    total = len(dias)
    yield 5

    # ── parámetros de captura Hi-DPI ──────────────────────────────────────
    WINDOW_W, WINDOW_H   = 2560, 1440      # tamaño de la ventana en px CSS
    DEVICE_SCALE         = 2               # —force-device-scale-factor
    TARGET_DISPLAY_WIDTH = 1920            # ancho final del <img>

    base_scale = (WINDOW_W * DEVICE_SCALE) / TARGET_DISPLAY_WIDTH  # ≈ 2.67
    dpi_scale  = base_scale * 0.6          # ≈ 1.60

    # ── Selenium headless ───────────────────────────────────────────────
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"--window-size={WINDOW_W},{WINDOW_H}")
    opts.add_argument(f"--force-device-scale-factor={DEVICE_SCALE}")
    service = Service("/usr/bin/chromedriver")
    driver  = webdriver.Chrome(service=service, options=opts)

    imgs_b64 = {}
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for idx, dia in enumerate(dias, 1):
            # ── generar mapa Folium con escalado de fuentes ────────────
            mapa = None
            for chunk in graficaTransportesDia(ciudad, dia, mes,
                                               sensibilidad_color, zoom,
                                               dpi_scale=dpi_scale):
                if not isinstance(chunk, int):
                    mapa = chunk

            # guardar HTML temporal
            tmp_html = tmpdir / f"{ciudad}_{mes}_{dia}.html"
            tmp_html.write_text(mapa.get_root().render(), encoding="utf-8")

            # capturar PNG
            driver.get(tmp_html.as_uri())
            time.sleep(3)      # espera tiles/fonts
            png_path = tmpdir / f"{ciudad}_{mes}_{dia}.png"
            driver.save_screenshot(str(png_path))

            # Base-64 para embebido
            imgs_b64[dia] = base64.b64encode(png_path.read_bytes()).decode("utf-8")

            # progreso (5 → 95)
            yield 5 + int(idx / total * 90)

    driver.quit()

    # ── construir HTML con slider ───────────────────────────────────────
    min_d, max_d = dias[0], dias[-1]
    imgs_json    = json.dumps({str(k): v for k, v in imgs_b64.items()})

    html_final = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"/>
<title>Mapas – {ciudad.capitalize()} {mes}</title>
<style>
 body{{margin:0;font-family:sans-serif;text-align:center}}
 #ctl{{position:absolute;top:20px;right:20px;background:#fff;padding:10px;
      border-radius:8px;box-shadow:0 0 10px rgba(0,0,0,.2);z-index:9999;
      font-size:14px}}
 #map-img{{width:100%;max-width:{TARGET_DISPLAY_WIDTH}px;height:auto}}
</style></head><body>
<div id="ctl">
  Día:
  <input type="range" id="slider" min="{min_d}" max="{max_d}" value="{min_d}"
         oninput="chg(this.value)">
  <span id="lbl">{min_d}</span>
</div>
<img id="map-img" src="data:image/png;base64,{imgs_b64[min_d]}" alt="Mapa"/>
<script>
const imgs={imgs_json};
function chg(v){{
  document.getElementById('lbl').textContent=v;
  document.getElementById('map-img').src='data:image/png;base64,'+imgs[v];
}}
</script></body></html>"""

    out.write_text(html_final, encoding="utf-8")
    yield 100
    yield out


# In[85]:

def comparar_mapas(ciudad_1, mes_1, sensibilidad_1,
                   ciudad_2, mes_2, sensibilidad_2,
                   zoom: int = 6):
    """
    Captura dos series de mapas diarios (960×1080 CSS px, escala 2×)
    SIN leyenda en las capturas y genera un HTML responsive con slider
    y ambos mapas lado a lado. Añade UNA sola leyenda global en el HTML.
    Progreso 0–100; al final devuelve el Path al HTML.
    """
    yield 0
    f1 = DATOS_DIR / f"{ciudad_1.lower()}-{int(mes_1):02}.xlsx"
    f2 = DATOS_DIR / f"{ciudad_2.lower()}-{int(mes_2):02}.xlsx"
    out = RESULTADOS_DIR / f"comparar_{ciudad_1}_{mes_1}_{ciudad_2}_{mes_2}.html"
    if not f1.exists() or not f2.exists():
        raise FileNotFoundError("Falta algún Excel")
    yield 5

    d1 = sorted(pd.read_excel(f1)["dia"].dropna().unique())
    d2 = sorted(pd.read_excel(f2)["dia"].dropna().unique())
    s_min, s_max = max(d1[0], d2[0]), min(d1[-1], d2[-1])
    if s_min > s_max:
        raise ValueError("No hay días comunes")
    dias = list(range(int(s_min), int(s_max) + 1))
    yield 15

    # Selenium headless 960×1080 CSS px, escala 2×
    CSS_W, CSS_H = 960, 1080
    DEV_SCALE    = 2
    dpi_scale    = 0.90

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"--window-size={CSS_W},{CSS_H}")
    opts.add_argument(f"--force-device-scale-factor={DEV_SCALE}")
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)
    yield 20

    L, R = {}, {}
    total = len(dias) * 2
    step  = 0

    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for dia in dias:
            # Mapa izquierdo SIN leyenda
            mapa1 = next(ch for ch in
                         graficaTransportesDia(
                             ciudad_1, dia, mes_1,
                             sensibilidad_1, zoom,
                             dpi_scale=dpi_scale,
                             legend_side=None
                         )
                         if not isinstance(ch, int))
            h1 = tmp / f"L_{dia}.html"
            h1.write_text(mapa1.get_root().render(), encoding="utf-8")
            driver.get(h1.as_uri()); time.sleep(2.2)
            p1 = tmp / f"L_{dia}.png"
            driver.save_screenshot(str(p1))
            L[str(dia)] = base64.b64encode(p1.read_bytes()).decode()
            step += 1; yield 20 + int(step / total * 75)

            # Mapa derecho SIN leyenda
            mapa2 = next(ch for ch in
                         graficaTransportesDia(
                             ciudad_2, dia, mes_2,
                             sensibilidad_2, zoom,
                             dpi_scale=dpi_scale,
                             legend_side=None
                         )
                         if not isinstance(ch, int))
            h2 = tmp / f"R_{dia}.html"
            h2.write_text(mapa2.get_root().render(), encoding="utf-8")
            driver.get(h2.as_uri()); time.sleep(2.2)
            p2 = tmp / f"R_{dia}.png"
            driver.save_screenshot(str(p2))
            R[str(dia)] = base64.b64encode(p2.read_bytes()).decode()
            step += 1; yield 20 + int(step / total * 75)

    driver.quit()
    yield 95

    # Construir HTML final con UNA sola leyenda
    legend_html = f"""
    <div style="
        position:fixed;
        bottom:10px;
        left:10px;
        width:260px;
        background:white;
        border:2px solid grey;
        border-radius:4px;
        padding:10px;
        font-size:13px;
        z-index:9999;
    ">
      <b>🗺️ Leyenda</b><br><br>
      <i style="background:#336699;width:12px;height:12px;display:inline-block;margin-right:5px;"></i>
        <b>Azul</b>: Provincias de origen<br>
      &nbsp;&nbsp;Más oscuro → más desplazamientos<br>
      <i style="background:#66f26a;width:12px;height:12px;display:inline-block;margin-right:5px;"></i>
        <b>Verde</b>: Provincia destino
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/>
<title>Comparación {ciudad_1} vs {ciudad_2}</title>
<style>
 html,body{{margin:0;padding:0;width:100vw;height:100vh;overflow:hidden}}
 #ctl{{position:fixed;top:10px;left:50%;transform:translateX(-50%);
       background:#fff;padding:6px 10px;border-radius:8px;
       box-shadow:0 0 6px #0004;font-family:sans-serif;font-size:14px;z-index:9}}
 .row{{display:flex;width:100vw;height:100vh}}
 .cell{{flex:0 0 50vw;height:100vh;overflow:hidden;position:relative}}
 .cell img{{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover}}
</style></head><body>
<div id="ctl">
 Día:
 <input type="range" id="sl" min="{s_min}" max="{s_max}" value="{s_min}"
        oninput="chg(this.value)">
 <span id="lbl">{s_min}</span>
</div>
<div class="row">
 <div class="cell"><img id="L" src="data:image/png;base64,{L[str(s_min)]}"></div>
 <div class="cell"><img id="R" src="data:image/png;base64,{R[str(s_min)]}"></div>
</div>
{legend_html}
<script>
const Limg=document.getElementById('L'),
      Rimg=document.getElementById('R'),
      lbl=document.getElementById('lbl'),
      L={json.dumps(L)}, R={json.dumps(R)};
function chg(v){{lbl.textContent=v;Limg.src='data:image/png;base64,'+L[v];
                 Rimg.src='data:image/png;base64,'+R[v];}}
</script></body></html>"""

    out.write_text(html, encoding="utf-8")
    yield 100
    yield out

# In[115]:


def mapa_transportes_relativo(ciudad, dia, mes, sensibilidad=3, open_browser=True):
    """
    Mapa Folium con viajes por mil habitantes.
    Funciona como generator: emite progreso (0–100) y al final la ruta al HTML.
    """
    geojson_path = DATOS_DIR / "georef-spain-provincia.geojson"
    trans_file   = DATOS_DIR / f"{ciudad.lower()}-{int(mes):02}.xlsx"
    pop_file     = DATOS_DIR / "poblaciones_provincias.xlsx"
    html_path    = RESULTADOS_DIR / f"relativo_{ciudad}_{mes}_{dia}.html"

    yield 0

    # Comprobaciones
    for path,label in [(geojson_path,"georef"),(trans_file,"transporte"),(pop_file,"poblaciones")]:
        if not path.exists():
            raise FileNotFoundError(f"{label} no encontrado: {path}")
    yield 10

    # Carga
    gdf = gpd.read_file(geojson_path)
    dfT = pd.read_excel(trans_file)
    dfP = pd.read_excel(pop_file)
    yield 25

    # Filtrar
    df_d = dfT[dfT["dia"]==dia]
    if df_d.empty:
        raise ValueError(f"No hay datos para día {dia}")
    yield 35

    # Agregar viajes
    df_agg = (
        df_d.groupby("provincia origen", as_index=False)["viajes"]
            .sum()
            .assign(prov_std=lambda d: d["provincia origen"].apply(standardize_province_name))
    )
    yield 45

    # Poblaciones
    dfP["prov_std"] = dfP["provincia"].apply(standardize_province_name)
    dfP = dfP[~dfP["prov_std"].isin(["portugal","france","francia"])]
    yield 55

    # Merge viajes+población
    df_rel = df_agg.merge(dfP[["prov_std","población"]], on="prov_std", how="left")
    df_rel["población"] = df_rel["población"].fillna(0)
    df_rel["relativo"] = df_rel.apply(
        lambda r: (r["viajes"]/r["población"])*1_000 if r["población"]>0 else 0, axis=1
    )
    df_rel["relativo_fmt"] = df_rel["relativo"].apply(lambda x: f"{x:.4f}")
    yield 65

    # Detectar campo
    campos = [c for c in gdf.columns if c.lower()!="geometry"]
    provs  = set(df_rel["prov_std"])
    best, maxm = None, 0
    for c in campos:
        m = gdf[c].astype(str).apply(standardize_province_name).isin(provs).sum()
        if m > maxm:
            best, maxm = c, m
    if best is None:
        raise RuntimeError("No se detectó campo provincia en el geojson")
    yield 75

    # Merge con geodataframe
    gdf["prov_std"] = gdf[best].astype(str).apply(standardize_province_name)
    gdfm = gdf.merge(df_rel[["prov_std","relativo","relativo_fmt"]], on="prov_std", how="left")
    gdfm["relativo"] = gdfm["relativo"].fillna(0)
    yield 85

    # Crear mapa y centrar
    center = gdfm.to_crs("EPSG:3857").geometry.centroid.unary_union.centroid
    ctr_ll = gpd.GeoSeries([center], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]
    m = folium.Map(location=[ctr_ll.y, ctr_ll.x], zoom_start=6)
    yield 90

    # Overlay superior
    tpl = """
    {% macro html(this,kwargs) -%}
    <div style="position:fixed; top:10px; left:50%; transform:translateX(-50%);
                background:white; padding:6px 12px; border:2px solid gray;
                border-radius:4px; font-size:13px; white-space:nowrap; z-index:9999;">
      Ciudad: {{this.c}} | Día: {{this.d}} | Mes: {{this.m}} | Sensib.: {{this.s}}
    </div>
    {%- endmacro %}
    """
    mc = MacroElement()
    mc._template = Template(tpl)
    mc.c, mc.d, mc.m, mc.s = ciudad, dia, mes, sensibilidad
    m.get_root().add_child(mc)

    # ======== AQUÍ REINSERTAMOS LA CAPA GeoJson =========
    estudio_std = standardize_province_name(ciudad)
    max_rel     = gdfm["relativo"].max() or 1
    def style_f(feat):
        prov = standardize_province_name(feat["properties"].get(best,""))
        if prov == estudio_std:
            return {"fillColor":"#66f26a","color":"blue","weight":1,"fillOpacity":1}
        r = feat["properties"].get("relativo",0)
        if r<=0:
            return {"fillColor":"#ffffff","color":"blue","weight":1,"fillOpacity":1}
        norm  = min(r/max_rel,1)
        inten = norm**(1/sensibilidad)
        R = 255-int(255*inten); G = 255-int(255*inten); B = 139-int(139*inten)
        return {"fillColor":f"#{R:02x}{G:02x}{B:02x}","color":"blue","weight":1,"fillOpacity":1}

    folium.GeoJson(
        gdfm,
        style_function=style_f,
        tooltip=folium.features.GeoJsonTooltip(
            fields=[best,"relativo_fmt"],
            aliases=["Provincia","Viajes/mil hab."]
        )
    ).add_to(m)

    yield 92  # GeoJson añadido

    # Leyenda
    legend_html = """
    <div style="
      position: fixed; 
      bottom: 10px; left: 10px; width: 240px; height: 130px;
      background-color: white; border:2px solid grey;
      border-radius:4px; padding: 10px; font-size: 13px; z-index:9999;
    ">
      <b>🗺️ Leyenda</b><br><br>
      <i style="background: #FFCC00; width: 12px; height: 12px; display:inline-block; margin-right:5px;"></i>
        <b>Amarillo</b>: Provincias origen<br>
      &nbsp;&nbsp;Más oscuro → Más viajes/mil hab.<br>
      <i style="background: #66f26a; width: 12px; height: 12px; display:inline-block; margin-right:5px;"></i>
        <b>Verde</b>: Provincia destino<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    yield 95  # leyenda añadida

    # Guardar, abrir y devolver
    m.save(html_path)
    if open_browser:
        webbrowser.open_new_tab(html_path.as_uri())
    yield html_path  # 100% final


# In[121]:


import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import imageio
import webbrowser
import time
from pathlib import Path
from tempfile import TemporaryDirectory

def exportar_mapa_gif(
    ciudad,
    mes,
    sensibilidad_color=10,
    zoom=6,
    duracion_segundos=0.1,
    open_browser=True,
    html_wrapper=True,
):
    """
    Genera un GIF animado de la evolución diaria:
    - Usa GeoPandas + Matplotlib para cada PNG 960×1080 px @100dpi.
    - Monta el GIF con imageio directamente.
    - Opcionalmente envuelve en un HTML.
    Progreso: 0–100. Devuelve Path al .gif o al HTML que lo envuelve.
    """
    excel_path = DATOS_DIR / f"{ciudad.lower()}-{int(mes):02}.xlsx"
    gif_path   = RESULTADOS_DIR / f"gif_{ciudad}_{int(mes):02}.gif"

    yield 0
    if not excel_path.exists():
        raise FileNotFoundError(excel_path)
    df = pd.read_excel(excel_path)
    if "dia" not in df.columns:
        raise ValueError("El Excel no contiene la columna 'dia'")
    dias = sorted(df["dia"].dropna().unique())
    if not dias:
        raise ValueError("No hay días disponibles")
    total = len(dias)
    yield 5

    # precarga geojson
    geojson = DATOS_DIR / "georef-spain-provincia.geojson"
    gdf_provincias = gpd.read_file(geojson)
    yield 10

    png_files = []
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        for idx, dia in enumerate(dias, start=1):
            # filtrar y agregar viajes
            df_dia = df[df["dia"] == dia]
            df_agg = (
                df_dia.groupby("provincia origen", as_index=False)["viajes"].sum()
                      .assign(prov_std=lambda d: d["provincia origen"]
                                                 .apply(standardize_province_name))
            )
            best = detectar_campo_provincia(gdf_provincias, df_agg)
            gdf = gdf_provincias.copy()
            gdf["prov_std"] = gdf[best].astype(str).apply(standardize_province_name)
            gdfm = gdf.merge(df_agg[["prov_std","viajes"]], on="prov_std", how="left")
            gdfm["viajes"] = gdfm["viajes"].fillna(0)
            max_v = gdfm["viajes"].max() or 1

            # preparar colores
            colors = [ get_fill_color(v, max_v, sensibilidad_color)
                       for v in gdfm["viajes"] ]

            # dibujar
            fig, ax = plt.subplots(figsize=(9.6,10.8), dpi=100)
            gdfm.plot(color=colors, edgecolor="blue", linewidth=0.5, ax=ax)
            ax.axis("off")
            ax.set_title(f"{ciudad.capitalize()} – Día {dia}", fontsize=14,
                         pad=12, backgroundcolor="white")

            # leyenda
            ley = fig.add_axes([0.02,0.02,0.25,0.12])
            ley.axis("off")
            ley.text(0,1,"🗺️ Leyenda", fontsize=12, weight="bold")
            ley.text(0,0.6,
                     "■ Azul: Origen\n"
                     "■ Oscuro→ más viajes\n"
                     "■ Verde: Destino",
                     fontsize=10)

            # guardar PNG
            png_path = tmpdir / f"{ciudad}_{dia}.png"
            fig.savefig(png_path, bbox_inches="tight")
            plt.close(fig)
            png_files.append(png_path)

            yield 10 + int(idx/total*80)

        # crear GIF
        fps = 1 / duracion_segundos
        with imageio.get_writer(gif_path, mode="I", fps=fps, loop=0) as writer:
            for p in png_files:
                writer.append_data(imageio.imread(str(p)))
        yield 90

    yield 95
    # HTML wrapper opcional
    if html_wrapper:
        html_file = RESULTADOS_DIR / f"gif_{ciudad}_{int(mes):02}.html"
        html_code = f"""<!DOCTYPE html>
<html lang="es"><meta charset="utf-8">
<title>GIF – {ciudad.capitalize()} {mes}</title>
<style>body{{margin:0;display:flex;justify-content:center;
             align-items:center;height:100vh;background:#000}}
       img{{max-width:100%;height:auto}}</style>
<body>
  <img src="{gif_path.name}" alt="GIF">
</body></html>"""
        html_file.write_text(html_code,encoding="utf-8")
        target = html_file
    else:
        target = gif_path

    if open_browser:
        webbrowser.open_new_tab(target.as_uri())

    yield 100
    yield target






# In[ ]:



