# Movilidad en festividades

Generador de mapas interactivos con una aplicación web en Streamlit. Usa datos de movilidad del Ministerio de Transportes para mostrar los flujos de viajeros entre provincias durante eventos como la Semana Santa, las Fallas o los Sanfermines.

## Qué permite hacer

- **Mapa interactivo de un día**: colorea las provincias según el volumen de viajes en un día concreto.
- **Mapa interactivo de un mes**: genera un HTML con todos los días y un control deslizante para navegar entre ellos.
- **Mapa mensual con imágenes**: versión del mapa del mes en imágenes.
- **Comparación de dos mapas**: compara dos ciudades o fechas.
- **Mapa relativo**: transporte por habitante, usando la población de cada provincia.
- **GIF animado de un mes**: animación de la evolución de los flujos.

## Datos

En `datos/` están los ficheros de movilidad en Excel por provincia (Valencia, Sevilla, Navarra, Cuenca y Murcia), la población por provincias y las delimitaciones provinciales en GeoJSON.

## Tecnologías

Python, Streamlit, pandas, GeoPandas, Folium (mapas interactivos), Shapely, Selenium (captura de los mapas para imágenes y GIF), ImageIO y openpyxl.

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Para exportar imágenes y GIF hace falta Chromium con su driver (`packages.txt` lista los paquetes para despliegue en Streamlit Cloud). La lógica de los mapas está en `funciones_app.py` y la interfaz en `streamlit_app.py`.
