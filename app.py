from pathlib import Path

# V3: la aplicación principal se mantiene como un cargador pequeño para evitar
# conflictos entre versiones antiguas del cotizador.
exec((Path(__file__).parent / "app_v3.py").read_text(encoding="utf-8"), globals())
