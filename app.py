import io
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

DB_PATH = Path(__file__).parent / "cotizador.db"

REPAIRS = [
    "Pantalla", "Batería", "Puerto de carga", "Flex de Encendido/Volumen",
    "Cámara Trasera", "Cámara Frontal", "Altavoz / Parlante", "Micrófono",
    "Placa Base (diagnóstico)", "IC de carga / soldadura", "Cambio de vidrio (glass)",
    "Sensor de huella", "Face ID / sensores", "Limpieza interna", "Flex Carga",
]

DEFAULT_LABOR = {
    "Pantalla": 55000, "Batería": 40000, "Puerto de carga": 60000,
    "Flex de Encendido/Volumen": 35000, "Cámara Trasera": 40000,
    "Cámara Frontal": 35000, "Altavoz / Parlante": 35000, "Micrófono": 35000,
    "Placa Base (diagnóstico)": 30000, "IC de carga / soldadura": 80000,
    "Cambio de vidrio (glass)": 70000, "Sensor de huella": 45000,
    "Face ID / sensores": 50000, "Limpieza interna": 30000, "Flex Carga": 45000,
}

BRANDS = [
    "APPLE", "IPHONE", "XIAOMI", "SAMSUNG", "MOTOROLA", "HUAWEI", "HONOR",
    "OPPO", "REALME", "VIVO", "INFINIX", "TECNO", "NOKIA", "LG", "KALLEY",
    "GOOGLE", "TCL", "ZTE", "ALCATEL", "ASUS", "ONEPLUS", "SONY", "LENOVO",
    "UMIDIGI", "BLU"
]


def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def money(v):
    return f"${int(round(v)):,.0f}".replace(",", ".")


def normalize(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clean_quality(text):
    q = normalize(text).upper()
    q = q.replace("INCELLL", "INCELL")
    q = re.sub(r"\bC\s*/\s*M\b", "CON MARCO", q)
    return q or "ESTÁNDAR"


def screen_quality(text):
    up = str(text or "").upper()
    tokens = []
    for token in ["SOFT OLED", "INCELL", "OLED", "LCD", "ORIGINAL", "GX", "JK", "CON MARCO", "C/M"]:
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", up):
            tokens.append("CON MARCO" if token == "C/M" else token)
    return clean_quality(" ".join(tokens))


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS providers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        delivery TEXT NOT NULL DEFAULT 'Envío',
        shipping INTEGER NOT NULL DEFAULT 0,
        travel INTEGER NOT NULL DEFAULT 0,
        note TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS references_(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        model TEXT NOT NULL,
        repair TEXT NOT NULL,
        quality TEXT DEFAULT '',
        provider_id INTEGER NOT NULL,
        cost INTEGER NOT NULL DEFAULT 0,
        note TEXT DEFAULT '',
        FOREIGN KEY(provider_id) REFERENCES providers(id)
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,data TEXT NOT NULL);
    """)
    c.execute(
        "INSERT OR IGNORE INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)",
        ("MarkBoss Repuestos", "Recogida presencial", 0, 12000, "Catálogo PDF")
    )
    defaults = {"margin_min": 18, "margin_rec": 30, "margin_prem": 45, "rounding": 1000, "bundle_labor": 75000}
    defaults.update({f"labor_{k}": v for k, v in DEFAULT_LABOR.items()})
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, str(v)))

    rows = c.execute("SELECT id,repair,quality FROM references_").fetchall()
    for r in rows:
        repair = normalize(r["repair"])
        quality = clean_quality(r["quality"])
        if repair.upper() in {"PANTALLA LCD", "DISPLAY LCD"}:
            quality = clean_quality("LCD " + quality)
            c.execute("UPDATE references_ SET repair='Pantalla', quality=? WHERE id=?", (quality, r["id"]))
        elif repair.upper() in {"PANTALLA OLED", "DISPLAY OLED"}:
            quality = clean_quality("OLED " + quality)
            c.execute("UPDATE references_ SET repair='Pantalla', quality=? WHERE id=?", (quality, r["id"]))
        elif repair.upper() in {"DISPLAY", "PANTALLA"}:
            c.execute("UPDATE references_ SET repair='Pantalla', quality=? WHERE id=?", (quality, r["id"]))

    dupes = c.execute("""
        SELECT lower(brand) b, lower(model) m, lower(repair) r, lower(quality) q, provider_id,
               MAX(id) keep_id, GROUP_CONCAT(id) ids
        FROM references_
        GROUP BY lower(brand), lower(model), lower(repair), lower(quality), provider_id
        HAVING COUNT(*) > 1
    """).fetchall()
    for d in dupes:
        for old_id in [int(x) for x in d["ids"].split(",") if int(x) != d["keep_id"]]:
            c.execute("DELETE FROM references_ WHERE id=?", (old_id,))
    c.commit()
    c.close()


def settings():
    return {r["key"]: float(r["value"]) for r in db().execute("SELECT key,value FROM settings")}


def providers():
    return db().execute("SELECT * FROM providers ORDER BY lower(name)").fetchall()


def refs():
    return db().execute("""
        SELECT r.*, p.name provider, p.delivery, p.shipping, p.travel
        FROM references_ r JOIN providers p ON p.id=r.provider_id
        ORDER BY lower(brand), lower(model), lower(repair), lower(quality), lower(provider)
    """).fetchall()


def upsert_reference(brand, model, repair, quality, provider_id, cost, note=""):
    brand, model = normalize(brand).upper(), normalize(model).upper()
    quality = clean_quality(quality)
    c = db()
    existing = c.execute("""
        SELECT id FROM references_
        WHERE lower(brand)=lower(?) AND lower(model)=lower(?)
        AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?
    """, (brand, model, repair, quality, provider_id)).fetchone()
    if existing:
        c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?", (int(cost), note.strip(), existing["id"]))
        action = "actualizada"
    else:
        c.execute("""
            INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note)
            VALUES(?,?,?,?,?,?,?)
        """, (brand, model, repair, quality, provider_id, int(cost), note.strip()))
        action = "nueva"
    c.commit(); c.close()
    return action


def parse_price(line):
    m = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,6})\s*$", line.strip())
    if not m:
        return None, line.strip()
    return int(m.group(1).replace(".", "").replace(",", "")), line[:m.start()].strip()


def parse_pdf(pdf_bytes):
    """Importa TODO el catálogo: displays y baterías.

    El PDF de MarkBoss contiene bloques separados de DISPLAY y BATERIA.
    El tipo de reparación se determina por el prefijo de cada línea; la variante
    solamente se utiliza para pantallas. Las líneas sin precio no se inventan.
    """
    if PdfReader is None:
        raise RuntimeError("Falta pypdf en requirements.txt")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    current_brand = ""
    rows, ignored = [], []

    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = normalize(raw)
            if not line:
                continue
            upper = line.upper()

            if "PRECIO" in upper and not re.match(r"^D?DISPLAY\b|^BATER[IÍ]A\b", upper):
                heading = re.sub(r"\bPRECIO\b", "", upper).strip()
                if heading:
                    current_brand = heading
                continue

            is_display = bool(re.match(r"^D?DISPLAY\b", upper))
            is_battery = bool(re.match(r"^BATER[IÍ]A\b", upper))
            if not (is_display or is_battery):
                continue

            cost, desc = parse_price(line)
            if cost is None:
                ignored.append((page_no, line, "sin precio"))
                continue

            if is_display:
                desc = re.sub(r"^D?DISPLAY\s+", "", desc, flags=re.I).strip()
                repair = "Pantalla"
                quality = screen_quality(desc)
                model = desc
                for token in [
                    "SOFT OLED", "INCELLL", "INCELL", "CON MARCO", "C/M",
                    "OLED", "ORIGINAL", "GX", "JK", "LCD"
                ]:
                    model = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", model, flags=re.I)
                model = normalize(model).strip(" -/").title()
            else:
                desc = re.sub(r"^BATER[IÍ]A\s+", "", desc, flags=re.I).strip()
                repair = "Batería"
                quality = "ESTÁNDAR"
                model = normalize(desc).strip(" -/").title()

            brand = normalize(current_brand).title() if current_brand else "Otra"
            if brand and model.upper().startswith(brand.upper() + " "):
                model = model[len(brand):].strip()
            if not model:
                ignored.append((page_no, line, "modelo vacío"))
                continue

            rows.append({
                "brand": brand,
                "model": model,
                "repair": repair,
                "quality": quality,
                "cost": cost,
                "page": page_no,
            })

    return rows, ignored


def import_rows(rows, provider_name):
    ps = list(providers())
    p = next((x for x in ps if x["name"].lower() == provider_name.lower()), None)
    if not p:
        c = db()
        c.execute("INSERT INTO providers(name,delivery,note) VALUES(?,?,?)", (provider_name, "Recogida presencial", "Importado automáticamente"))
        c.commit(); c.close()
        p = next(x for x in providers() if x["name"].lower() == provider_name.lower())
    added = updated = 0
    for r in rows:
        action = upsert_reference(
            r["brand"], r["model"], r["repair"], r["quality"], p["id"],
            r["cost"], f"PDF MarkBoss · página {r.get('page','')}"
        )
        if action == "nueva":
            added += 1
        else:
            updated += 1
    return added, updated


def normalize_whatsapp_line(line):
    clean = re.sub(r"[^\w\s/+.\-$]", " ", line, flags=re.UNICODE)
    m = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,6})\s*$", clean.strip())
    if not m:
        return None
    cost = int(m.group(1).replace(".", "").replace(",", ""))
    desc = clean[:m.start()].strip()
    up = desc.upper()
    if "BATER" in up:
        repair = "Batería"
        quality = "ESTÁNDAR"
    elif any(x in up for x in ["LCD", "INCELL", "DISPLAY", "PANTALL", "OLED", "GX", "JK"]):
        repair = "Pantalla"
        quality = screen_quality(up)
    else:
        return None
    brand = next((b.title() for b in BRANDS if re.search(rf"\b{re.escape(b)}\b", up)), "Otra")
    model = re.sub(r"\bDISPLAY\b|\bPANTALLA\b|\bBATER[IÍ]A\b", " ", desc, flags=re.I)
    for token in ["SOFT OLED", "OLED", "LCD", "INCELL", "C/M", "CON MARCO", "GX", "JK", "ORIGINAL"]:
        model = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", model, flags=re.I)
    model = normalize(model).title()
    return {"brand": brand, "model": model, "repair": repair, "quality": clean_quality(quality), "cost": cost}


def calculate(items):
    s = settings()
    parts = sum(int(x["cost"]) for x in items)
    ps = {p["id"]: p for p in providers()}
    logistics = 0
    for pid in {x["provider_id"] for x in items}:
        p = ps[pid]
        if p["delivery"] in ("Recogida presencial", "Ambos"):
            logistics += int(p["shipping"] or 0) + int(p["travel"] or 0)
        else:
            logistics += int(p["shipping"] or 0)
    override = int(st.session_state.get("labor_override", 0))
    default = int(s.get("bundle_labor", 75000)) if len(items) > 1 else int(s.get(f"labor_{items[0]['repair']}", 40000)) if items else 0
    labor = override or default
    base = parts + logistics + labor
    rnd = int(s.get("rounding", 1000)) or 1
    price = lambda m: round((base * (1 + m / 100)) / rnd) * rnd
    return parts, logistics, labor, base, price(s["margin_min"]), price(s["margin_rec"]), price(s["margin_prem"])


def add_quote(r):
    if r["id"] not in [x["id"] for x in st.session_state.quote]:
        st.session_state.quote.append(dict(r))


def reset_quote():
    st.session_state.quote = []
    st.session_state.labor_override = 0


def history_equipment(data):
    items = data.get("items", [])
    if not items:
        return "Equipo no especificado"
    first = items[0]
    equipment = f"{first.get('brand', '').strip()} {first.get('model', '').strip()}".strip()
    return equipment or "Equipo no especificado"


def history_repairs(data):
    items = data.get("items", [])
    repairs = []
    for item in items:
        repair = str(item.get("repair", "")).strip()
        quality = str(item.get("quality", "")).strip()
        text = f"{repair} ({quality})" if quality and quality != "ESTÁNDAR" else repair
        if text and text not in repairs:
            repairs.append(text)
    return ", ".join(repairs) or "Reparación no especificada"


st.set_page_config(page_title="BLACK TECH · Cotizador", page_icon="💰", layout="wide", initial_sidebar_state="collapsed")
init_db()
if "quote" not in st.session_state:
    st.session_state.quote = []
if "labor_override" not in st.session_state:
    st.session_state.labor_override = 0

st.markdown("""
<style>
.block-container{max-width:1180px;padding:1rem 1rem 4rem}
.hero{background:linear-gradient(135deg,#0f172a,#1e293b 62%,#2563eb);color:#fff;padding:20px 22px;border-radius:20px;margin-bottom:14px;box-shadow:0 8px 28px rgba(15,23,42,.14)}
.hero h1{margin:0;font-size:1.9rem;letter-spacing:.08em}.hero p{margin:4px 0 0;color:#cbd5e1}
.navbox{background:#f8fafc;border:1px solid #e2e8f0;padding:10px 12px;border-radius:16px;margin-bottom:18px}
.big-result{background:linear-gradient(135deg,#eff6ff,#fff);border:2px solid #2563eb;border-radius:18px;padding:18px;text-align:center;margin:14px 0}.big-result .value{font-size:2.25rem;font-weight:800;color:#1d4ed8}.big-result .label{color:#64748b;font-size:.88rem}
.reference-box{background:#f8fafc;border:1px solid #e2e8f0;border-radius:16px;padding:12px 14px;margin:8px 0 14px}
.history-card{border:1px solid #e2e8f0;border-radius:16px;padding:14px;margin:8px 0;background:#fff}
.history-title{font-size:1.05rem;font-weight:750;margin-bottom:3px}.history-meta{color:#64748b;font-size:.88rem}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>BLACK TECH</h1><p>Cotizador profesional de reparaciones</p></div>', unsafe_allow_html=True)

pages = ["💰 Cotizar", "📚 Referencias", "📄 Catálogo PDF", "📱 WhatsApp", "🚚 Proveedores", "⚙️ Configuración", "🧾 Historial"]
st.markdown('<div class="navbox">', unsafe_allow_html=True)
page = st.selectbox("Módulo", pages, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)
allrefs = list(refs())

if page == "💰 Cotizar":
    st.header("Nueva cotización")
    st.caption("Marca y modelo son listas dependientes; el tipo de reparación controla qué repuestos aparecen.")
    brands = sorted(set(r["brand"] for r in allrefs), key=str.lower)
    a, b = st.columns(2)
    brand = a.selectbox("Marca", [""] + brands, format_func=lambda x: "Selecciona una marca..." if not x else x, key="q_brand")
    models = sorted(set(r["model"] for r in allrefs if not brand or r["brand"].lower() == brand.lower()), key=str.lower)
    model = b.selectbox("Modelo", [""] + models, format_func=lambda x: "Selecciona un modelo..." if not x else x, key="q_model")
    available = [r for r in allrefs if (not brand or r["brand"].lower() == brand.lower()) and (not model or r["model"].lower() == model.lower())]

    repair = st.selectbox("Tipo de reparación", [""] + REPAIRS, format_func=lambda x: "Selecciona el tipo de reparación..." if not x else x, key="q_repair")
    matches = [r for r in available if r["repair"].lower() == repair.lower()] if repair else []

    if matches:
        st.markdown('<div class="reference-box">', unsafe_allow_html=True)
        st.caption("Selecciona la referencia exacta del repuesto")
        labels = [f"{r['quality'] or 'ESTÁNDAR'} · {r['provider']} · {money(r['cost'])}" for r in matches]
        if hasattr(st, "pills"):
            selected_label = st.pills("Referencia", labels, selection_mode="single", label_visibility="collapsed", key="q_ref_pills")
            selected = matches[labels.index(selected_label)] if selected_label in labels else None
        else:
            idx = st.selectbox("Referencia", range(len(matches)), format_func=lambda i: labels[i], key="q_ref")
            selected = matches[idx]
        if selected:
            x, y = st.columns([4, 1])
            x.write(f"**{selected['quality'] or 'ESTÁNDAR'}** · {selected['provider']}")
            y.write(f"**{money(selected['cost'])}**")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("＋ Agregar reparación al cálculo", type="primary", use_container_width=True, disabled=selected is None):
            add_quote(selected); st.rerun()
    elif repair:
        st.info("Este tipo de reparación está disponible en el cotizador, pero todavía no tiene una referencia de repuesto registrada para este modelo.")

    if st.session_state.quote:
        st.divider(); st.subheader("Reparaciones agregadas")
        for i, r in enumerate(st.session_state.quote):
            with st.container(border=True):
                x, y, z = st.columns([5, 2, 1])
                x.write(f"**{r['repair']} · {r['quality'] or 'ESTÁNDAR'}**")
                x.caption(f"{r['brand']} {r['model']} · {r['provider']}")
                y.write(money(r["cost"]))
                if z.button("Quitar", key=f"remove_{i}"):
                    st.session_state.quote.pop(i); st.rerun()
        default_labor = calculate(st.session_state.quote)[2]
        if st.session_state.get("labor_override", 0) == 0:
            st.session_state.labor_override = int(default_labor)
        st.number_input("Mano de obra", min_value=0, step=1000, key="labor_override")
        parts, logistics, labor, base, pmin, prec, pprem = calculate(st.session_state.quote)
        a, b, c = st.columns(3)
        a.metric("Repuestos", money(parts)); b.metric("Logística", money(logistics)); c.metric("Mano de obra", money(labor))
        st.markdown(f'<div class="big-result"><div class="label">COSTO REAL</div><div class="value">{money(base)}</div></div>', unsafe_allow_html=True)
        a, b, c = st.columns(3)
        a.metric("Mínimo", money(pmin)); b.metric("RECOMENDADO", money(prec)); c.metric("Premium", money(pprem))
        a, b = st.columns(2)
        if a.button("Guardar cotización", type="primary", use_container_width=True):
            payload = {
                "items": [dict(x) for x in st.session_state.quote],
                "parts": parts,
                "logistics": logistics,
                "labor": labor,
                "base": base,
                "recommended": prec,
                "premium": pprem,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
            }
            cdb = db(); cdb.execute("INSERT INTO history(created_at,data) VALUES(?,?)", (datetime.now().isoformat(timespec="seconds"), json.dumps(payload, ensure_ascii=False))); cdb.commit(); cdb.close()
            st.success("Cotización guardada en el historial.")
        if b.button("Limpiar cotización", use_container_width=True):
            reset_quote(); st.rerun()
    else:
        st.info("Selecciona una reparación y una referencia para agregarla al cálculo.")

elif page == "📚 Referencias":
    st.header("Catálogo de referencias")
    st.caption("Tipo de reparación y variante están separados. Ejemplo: Pantalla → OLED / LCD / INCELL / GX / JK / CON MARCO.")
    ps = list(providers()); provider_names = [p["name"] for p in ps]
    if ps:
        with st.form("new_ref"):
            brands_existing = sorted(set(r["brand"] for r in allrefs), key=str.lower)
            brand = st.selectbox("Marca", ["＋ Nueva marca..."] + brands_existing, key="r_brand")
            brand_manual = st.text_input("Nueva marca") if brand.startswith("＋") else brand
            models_existing = sorted(set(r["model"] for r in allrefs if r["brand"].lower() == brand_manual.lower()), key=str.lower)
            model = st.selectbox("Modelo", ["＋ Nuevo modelo..."] + models_existing, key="r_model")
            model_manual = st.text_input("Nuevo modelo") if model.startswith("＋") else model
            a, b = st.columns(2)
            repair = a.selectbox("Tipo de reparación", REPAIRS, key="r_repair")
            quality = b.text_input("Variante / calidad", placeholder="OLED, LCD, INCELL, CON MARCO, GX, JK...")
            a, b = st.columns(2)
            provider_name = a.selectbox("Proveedor", provider_names)
            cost = b.number_input("Costo", min_value=0, step=1000)
            note = st.text_area("Nota")
            if st.form_submit_button("Guardar / actualizar referencia", type="primary", use_container_width=True):
                bc = (brand_manual if brand.startswith("＋") else brand).strip()
                mc = (model_manual if model.startswith("＋") else model).strip()
                if not bc or not mc or cost <= 0:
                    st.error("Marca, modelo y costo son obligatorios.")
                else:
                    pid = next(p["id"] for p in ps if p["name"] == provider_name)
                    action = upsert_reference(bc, mc, repair, quality, pid, cost, note)
                    st.success(f"Referencia {action} correctamente."); st.rerun()
    q = st.text_input("Buscar referencias", placeholder="Ej. IPHONE 13, OLED, CON MARCO...")
    data = [x for x in refs() if q.strip().lower() in " ".join(str(x[k] or "") for k in ["brand", "model", "repair", "quality", "provider"]).lower()]
    st.caption(f"{len(data)} referencia(s) encontrada(s).")
    for r in data:
        with st.expander(f"{r['brand']} · {r['model']} · {r['repair']} · {r['quality'] or 'ESTÁNDAR'} · {r['provider']}"):
            st.write(f"**Costo:** {money(r['cost'])}")
            st.caption(r["note"] or "Sin nota")

elif page == "📄 Catálogo PDF":
    st.header("Importar catálogo de MarkBoss")
    st.caption("Importa pantallas y baterías. En pantallas, LCD/OLED/INCELL/GX/JK/CON MARCO son variantes; las baterías quedan como tipo Batería.")
    uploaded = st.file_uploader("PDF de precios", type=["pdf"], key="pdf_upload")
    if uploaded and not uploaded.name.lower().endswith(".pdf"):
        st.error("El archivo seleccionado no parece ser un PDF válido.")
        uploaded = None
    if uploaded:
        if st.button("Analizar PDF", type="primary", use_container_width=True):
            try:
                rows, ignored = parse_pdf(uploaded.getvalue())
                st.session_state.pdf_rows = rows
                st.session_state.pdf_ignored = ignored
                screens = sum(1 for r in rows if r["repair"] == "Pantalla")
                batteries = sum(1 for r in rows if r["repair"] == "Batería")
                st.success(f"Encontradas {len(rows)} referencias con precio: {screens} pantallas y {batteries} baterías. {len(ignored)} líneas sin precio fueron omitidas.")
            except Exception as e:
                st.error(f"No se pudo analizar el PDF: {e}")
        rows = st.session_state.get("pdf_rows", [])
        if rows:
            st.dataframe([
                {"Marca":r["brand"], "Modelo":r["model"], "Tipo":r["repair"], "Variante":r["quality"], "Precio":money(r["cost"]), "Página":r["page"]}
                for r in rows
            ], use_container_width=True, hide_index=True)
            if st.button("Importar / actualizar catálogo MarkBoss", type="primary", use_container_width=True):
                a, u = import_rows(rows, "MarkBoss Repuestos")
                st.success(f"Catálogo actualizado: {a} nuevas · {u} actualizadas.")
                st.session_state.pdf_rows = []
                st.rerun()

elif page == "📱 WhatsApp":
    st.header("Carga rápida por WhatsApp")
    st.caption("Las líneas reconocidas se clasifican automáticamente como pantalla o batería.")
    ps = list(providers()); provider_names = [p["name"] for p in ps]
    if not provider_names:
        st.warning("Crea primero un proveedor.")
    else:
        provider_name = st.selectbox("Proveedor", provider_names)
        text = st.text_area("Lista de WhatsApp", height=240, placeholder="Xiaomi Redmi 13 INCELL 42.000\nXiaomi Redmi 13 BATERIA 25.000")
        if st.button("Analizar lista", type="primary", use_container_width=True):
            parsed = [normalize_whatsapp_line(x) for x in text.splitlines()]
            st.session_state.wa_rows = [x for x in parsed if x]
            st.success(f"Se reconocieron {len(st.session_state.wa_rows)} líneas.")
        rows = st.session_state.get("wa_rows", [])
        if rows:
            st.dataframe([
                {"Marca":r["brand"], "Modelo":r["model"], "Tipo":r["repair"], "Variante":r["quality"], "Costo":money(r["cost"])}
                for r in rows
            ], use_container_width=True, hide_index=True)
            if st.button("Guardar / actualizar referencias", type="primary", use_container_width=True):
                a, u = import_rows(rows, provider_name)
                st.success(f"Guardado: {a} nuevas · {u} actualizadas.")
                st.session_state.wa_rows = []
                st.rerun()

elif page == "🚚 Proveedores":
    st.header("Proveedores")
    for p in providers():
        with st.expander(p["name"]):
            with st.form(f"provider_{p['id']}"):
                name = st.text_input("Nombre", p["name"])
                delivery = st.selectbox("Entrega", ["Recogida presencial", "Envío", "Ambos"], index=["Recogida presencial", "Envío", "Ambos"].index(p["delivery"]))
                a, b = st.columns(2)
                shipping = a.number_input("Envío", min_value=0, step=1000, value=int(p["shipping"]))
                travel = b.number_input("Desplazamiento", min_value=0, step=1000, value=int(p["travel"]))
                note = st.text_area("Nota", p["note"] or "")
                if st.form_submit_button("Guardar cambios", use_container_width=True):
                    c = db(); c.execute("UPDATE providers SET name=?,delivery=?,shipping=?,travel=?,note=? WHERE id=?", (name.strip(), delivery, shipping, travel, note, p["id"])); c.commit(); c.close(); st.rerun()
    st.divider()
    with st.form("new_provider"):
        name = st.text_input("Nuevo proveedor")
        delivery = st.selectbox("Entrega", ["Recogida presencial", "Envío", "Ambos"])
        a, b = st.columns(2)
        shipping = a.number_input("Envío", min_value=0, step=1000)
        travel = b.number_input("Desplazamiento", min_value=0, step=1000)
        note = st.text_area("Nota")
        if st.form_submit_button("Agregar proveedor", use_container_width=True):
            if not name.strip():
                st.error("Escribe el nombre del proveedor.")
            else:
                c = db(); c.execute("INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)", (name.strip(), delivery, shipping, travel, note)); c.commit(); c.close(); st.rerun()

elif page == "⚙️ Configuración":
    st.header("Configuración")
    s = settings()
    a, b, c = st.columns(3)
    mn = a.number_input("Margen mínimo %", value=float(s["margin_min"]), step=1.0)
    mr = b.number_input("Margen recomendado %", value=float(s["margin_rec"]), step=1.0)
    mp = c.number_input("Margen premium %", value=float(s["margin_prem"]), step=1.0)
    a, b = st.columns(2)
    rnd = a.number_input("Redondeo", min_value=1, value=int(s["rounding"]), step=1000)
    bundle = b.number_input("Mano de obra 2+ reparaciones", min_value=0, value=int(s["bundle_labor"]), step=1000)
    st.subheader("Mano de obra por tipo")
    labor_values = {}
    cols = st.columns(2)
    for i, repair_name in enumerate(REPAIRS):
        labor_values[repair_name] = cols[i % 2].number_input(repair_name, min_value=0, value=int(s.get(f"labor_{repair_name}", DEFAULT_LABOR[repair_name])), step=1000, key=f"labor_cfg_{i}")
    if st.button("Guardar configuración", type="primary", use_container_width=True):
        cdb = db()
        for k, v in [("margin_min", mn), ("margin_rec", mr), ("margin_prem", mp), ("rounding", rnd), ("bundle_labor", bundle)]:
            cdb.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
        for repair_name, value in labor_values.items():
            cdb.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"labor_{repair_name}", str(value)))
        cdb.commit(); cdb.close(); st.success("Configuración guardada.")

elif page == "🧾 Historial":
    st.header("Historial de reparaciones")
    st.caption("Esta sección ahora funciona como una base de consulta: busca un modelo y revisa qué reparaciones, repuestos y costos se usaron anteriormente.")

    search = st.text_input(
        "Buscar equipo o reparación",
        placeholder="Ej. Redmi 13, iPhone 13, pantalla, batería...",
        key="history_search",
    )

    rows = db().execute("SELECT * FROM history ORDER BY id DESC").fetchall()
    history_items = []
    term = search.strip().lower()
    for r in rows:
        data = json.loads(r["data"])
        equipment = history_equipment(data)
        repairs = history_repairs(data)
        haystack = " ".join([
            equipment,
            repairs,
            " ".join(str(x.get("quality", "")) for x in data.get("items", [])),
        ]).lower()
        if not term or term in haystack:
            history_items.append((r, data, equipment, repairs))

    total = len(history_items)
    st.caption(f"{total} cotización(es) encontrada(s).")

    if not rows:
        st.info("Todavía no hay cotizaciones guardadas.")
    elif not history_items:
        st.warning("No encontramos una cotización que coincida con esa búsqueda.")
    else:
        for r, data, equipment, repairs in history_items:
            with st.container(border=True):
                st.markdown(
                    f'<div class="history-title">📱 {equipment}</div>'
                    f'<div class="history-meta">📅 {r["created_at"]} · 🛠️ {repairs}</div>',
                    unsafe_allow_html=True,
                )
                a, b, c = st.columns(3)
                a.metric("Repuestos", money(data.get("parts", 0)))
                b.metric("Costo real", money(data.get("base", 0)))
                c.metric("Recomendado", money(data.get("recommended", 0)))

                with st.expander("Ver repuestos y detalles"):
                    for item in data.get("items", []):
                        quality = item.get("quality") or "ESTÁNDAR"
                        st.write(
                            f"• **{item.get('repair', 'Reparación')}** · "
                            f"{quality} · {item.get('provider', 'Proveedor no registrado')} · "
                            f"{money(item.get('cost', 0))}"
                        )
                    st.write(
                        f"**Logística:** {money(data.get('logistics', 0))} · "
                        f"**Mano de obra:** {money(data.get('labor', 0))} · "
                        f"**Premium:** {money(data.get('premium', 0))}"
                    )
