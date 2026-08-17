# COTIZADOR-REPARACIONES

Base de precios inteligente para BLACK TECH, desarrollada con **Streamlit**.

## V1

- Cotizar una o varias reparaciones en el mismo cálculo.
- Filtrar por marca, modelo y tipo de reparación.
- Elegir la variante exacta del repuesto: por ejemplo **LCD normal** o **LCD con marco**.
- Administrar proveedores y costos de envío/desplazamiento.
- Base de mano de obra por tipo de reparación.
- Mano de obra especial para reparaciones combinadas.
- Precio mínimo, recomendado y premium.
- Historial y respaldo JSON.
- Compatible con PC y celular mediante Streamlit.

## Ejecución

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Persistencia

La V1 utiliza SQLite (`cotizador.db`) para guardar referencias, proveedores, configuración e historial.

**Importante:** en Streamlit Community Cloud el almacenamiento local puede no ser permanente entre reinicios/redeploys. Para una versión multi-dispositivo con datos permanentes añadiremos posteriormente una base externa o almacenamiento sincronizado.

## Datos de prueba

Se precargan las referencias reales para probar el Redmi 13:

- Pantalla LCD — $35.000
- Pantalla LCD con marco — $38.000
- Batería — $25.000
- MarkBoss Repuestos — desplazamiento $12.000
