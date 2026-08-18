import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

DB_PATH = Path(__file__).parent / "cotizador.db"
REPAIRS = [
    "Pantalla OLED", "Pantalla LCD", "Batería", "Puerto de carga",
    "Flex de Encendido/Volumen", "Cámara Trasera", "Cámara Frontal",
    "Altavoz / Parlante", "Micrófono", "Placa Base (diagnóstico)",
    "IC de carga / soldadura", "Cambio de vidrio (glass)", "Sensor de huella",
    "Face ID / sensores", "Limpieza interna", "Flex Carga"
]
DEFAULT_LABOR = {
    "Pantalla OLED": 65000, "Pantalla LCD": 55000, "Batería": 40000,
    "Puerto de carga": 60000, "Flex de Encendido/Volumen": 35000,
    "Cámara Trasera": 40000, "Cámara Frontal": 35000,
    "Altavoz / Parlante": 35000, "Micrófono": 35000,
    "Placa Base (diagnóstico)": 30000, "IC de carga / soldadura": 80000,
    "Cambio de vidrio (glass)": 70000, "Sensor de huella": 45000,
    "Face ID / sensores": 50000, "Limpieza interna": 30000, "Flex Carga": 45000,
}


def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


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
    if c.execute("SELECT COUNT(*) n FROM providers").fetchone()["n"] == 0:
        c.execute(
            "INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)",
            ("MarkBoss Repuestos", "Recogida presencial", 0, 12000, "Desplazamiento estimado.")
        )
    defaults = {"margin_min": 18, "margin_rec": 30, "margin_prem": 45, "rounding": 1000, "bundle_labor": 75000}
    defaults.update({f"labor_{k}": v for k, v in DEFAULT_LABOR.items()})
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, str(v)))
    c.commit()
    c.close()


def settings():
    return {r["key"]: float(r["value"]) for r in db().execute("SELECT key,value FROM settings")}


def money(v):
    return f"${int(round(v)):,.0f}".replace(",", ".")


def refs():
    return db().execute(
        "SELECT r.*,p.name provider,p.delivery,p.shipping,p.travel "
        "FROM references_ r JOIN providers p ON p.id=r.provider_id "
        "ORDER BY brand,model,repair,quality"
    ).fetchall()


def providers():
    return db().execute("SELECT * FROM providers ORDER BY name").fetchall()


def save_setting(k, v):
    c = db()
    c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    c.commit()
    c.close()


def reset_quote():
    st.session_state.quote = []
    st.session_state.labor_override = 0


def add_quote(r):
    if r["id"] not in [x["id"] for x in st.session_state.quote]:
        st.session_state.quote.append(dict(r))


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
    if override:
        labor = override
    elif len(items) > 1:
        labor = int(s.get("bundle_labor", 75000))
    elif items:
        labor = int(s.get(f"labor_{items[0]['repair']}", DEFAULT_LABOR.get(items[0]["repair"], 40000)))
    else:
        labor = 0
    base = parts + logistics + labor
    rnd = int(s.get("rounding", 1000)) or 1
    price = lambda m: round((base * (1 + m / 100)) / rnd) * rnd
    return parts, logistics, labor, base, price(s["margin_min"]), price(s["margin_rec"]), price(s["margin_prem"])


def normalize_text(s):
    return re.sub(r"\s+", " ", s or "").strip()


def clean_model_quality(text):
    text = normalize_text(text)
    quality_tokens = [
        "SOFT OLED", "OLED", "INCELL", "INCELLL", "ORIGINAL", "GX", "JK",
        "C/M", "CM", "CON MARCO"
    ]
    quality = []
    work = text
    for token in quality_tokens:
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, work, flags=re.I):
            quality.append("C/M" if token in ("CM", "CON MARCO") else ("INCELL" if token == "INCELLL" else token))
            work = re.sub(pattern, " ", work, flags=re.I)
    return normalize_text(work), " ".join(dict.fromkeys(quality))


def parse_markboss_pdf(uploaded_file):
    if PdfReader is None:
        raise RuntimeError("Falta la dependencia pypdf. Agrega pypdf a requirements.txt.")
    reader = PdfReader(uploaded_file)
    current_brand = None
    rows = []
    skipped = 0
    brand_names = {
        "GOOGLE", "HUAWEI", "INFINIX", "IPHONE", "KALLEY", "LG", "MOTOROLA",
        "NOKIA", "OPPO", "REALME", "SAMSUNG", "TECNO", "TCL", "VIVO", "XIAOMI",
        "ZTE", "ALCATEL", "ASUS", "HONOR", "ONEPLUS", "SONY"
    }
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = normalize_text(raw).upper()
            if not line or line in ("LISTADO DE VENTAS", "PRECIO") or "WHARSAPP" in line or "WHATSAPP" in line:
                continue
            if line in brand_names:
                current_brand = line
                continue
            if line.endswith(" PRECIO") and line.split()[0] in brand_names:
                current_brand = line.split()[0]
                continue
            if not line.startswith("DISPLAY ") or not current_brand:
                continue
            body = normalize_text(line[8:])
            m = re.search(r"(?:^|\s)(\d{1,3}(?:\.\d{3})+|\d{4,6})$", body)
            if not m:
                skipped += 1
                continue
            price = int(m.group(1).replace(".", ""))
            descriptor = body[:m.start()].strip()
            if descriptor.upper().startswith(current_brand + " "):
                descriptor = descriptor[len(current_brand):].strip()
            model, quality = clean_model_quality(descriptor)
            if not model or price <= 0:
                skipped += 1
                continue
            rows.append({"brand": current_brand, "model": model, "repair": "Pantalla", "quality": quality, "cost": price})
    return rows, skipped


def import_rows(rows, provider_id):
    c = db()
    inserted = updated = 0
    for row in rows:
        existing = c.execute(
            "SELECT id FROM references_ WHERE lower(brand)=lower(?) AND lower(model)=lower(?) "
            "AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?",
            (row["brand"], row["model"], row["repair"], row["quality"], provider_id)
        ).fetchone()
        if existing:
            c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?", (row["cost"], "Importado desde PDF MarkBoss", existing["id"]))
            updated += 1
        else:
            c.execute(
                "INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",
                (row["brand"], row["model"], row["repair"], row["quality"], provider_id, row["cost"], "Importado desde PDF MarkBoss")
            )
            inserted += 1
    c.commit()
    c.close()
    return inserted, updated


st.set_page_config(page_title="BLACK TECH · Cotizador", page_icon="💰", layout="wide", initial_sidebar_state="collapsed")
init_db()
if "quote" not in st.session_state:
    st.session_state.quote = []
if "labor_override" not in st.session_state:
    st.session_state.labor_override = 0

st.markdown("""
<style>
.block-container{max-width:1180px;padding-top:1.4rem;padding-bottom:4rem}
.hero{background:linear-gradient(135deg,#111827 0%,#1f2937 65%,#2563eb 100%);color:white;padding:24px 26px;border-radius:18px;margin-bottom:20px;box-shadow:0 8px 28px rgba(15,23,42,.15)}
.hero h1{margin:0;font-size:2rem;letter-spacing:.08em}.hero p{margin:5px 0 0;color:#cbd5e1}
.big-result{background:linear-gradient(135deg,#eff6ff,#fff);border:2px solid #2563eb;border-radius:18px;padding:20px;text-align:center;margin:14px 0}.big-result .value{font-size:2.2rem;font-weight:800;color:#1d4ed8}.big-result .label{color:#64748b;font-size:.9rem}
.import-card{border:1px solid #dbeafe;background:#f8fbff;border-radius:16px;padding:18px;margin-bottom:16px}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>BLACK TECH</h1><p>Cotizador profesional de reparaciones · costos, logística y precio recomendado</p></div>', unsafe_allow_html=True)
page = st.sidebar.radio("Menú", ["Cotizar", "Referencias", "Proveedores", "Configuración", "Historial"])

allrefs = list(refs())
brands = sorted({r["brand"] for r in allrefs})

if page == "Cotizar":
    st.header("¿Cuánto cobrar?")
    st.caption("Selecciona primero la marca y el modelo. El catálogo se alimenta de tus proveedores.")
    if not allrefs:
        st.info("Aún no hay referencias. Importa el PDF de MarkBoss desde Referencias.")
    else:
        a, b = st.columns(2)
        brand = a.selectbox("Marca", ["Selecciona una marca..."] + brands, key="q_brand_select")
        brand_value = "" if brand.startswith("Selecciona") else brand
        model_options = sorted({r["model"] for r in allrefs if not brand_value or r["brand"] == brand_value})
        model = b.selectbox("Modelo / referencia", ["Selecciona un modelo..."] + model_options, key="q_model_select")
        model_value = "" if model.startswith("Selecciona") else model
        repair_options = sorted({r["repair"] for r in allrefs if (not brand_value or r["brand"] == brand_value) and (not model_value or r["model"] == model_value)} | set(REPAIRS))
        repair = st.selectbox("Tipo de reparación", ["Selecciona el tipo..."] + repair_options, key="q_repair")
        repair_value = "" if repair.startswith("Selecciona") else repair
        matches = [r for r in allrefs if (not brand_value or r["brand"] == brand_value) and (not model_value or r["model"] == model_value) and (not repair_value or r["repair"] == repair_value)]
        if matches:
            labels = [f"{r['quality'] or 'Sin variante'} · {r['provider']} · {money(r['cost'])}" for r in matches]
            idx = st.selectbox("Variante / proveedor", range(len(matches)), format_func=lambda i: labels[i], key="q_ref")
            selected = matches[idx]
            st.info(f"{selected['brand']} {selected['model']} · {selected['repair']} · {selected['quality'] or 'Sin variante'} · {selected['provider']} · {money(selected['cost'])}")
            if st.button("＋ Agregar reparación al cálculo", type="primary", use_container_width=True):
                add_quote(selected)
                st.rerun()
        elif brand_value or model_value or repair_value:
            st.warning("No hay referencias guardadas que coincidan con esta combinación.")

    if st.session_state.quote:
        st.divider()
        st.subheader("Reparaciones agregadas")
        for i, r in enumerate(st.session_state.quote):
            with st.container(border=True):
                x, y, z = st.columns([5, 2, 1])
                x.write(f"**{r['repair']} · {r['quality'] or 'Sin variante'}**")
                x.caption(f"{r['brand']} {r['model']} · {r['provider']}")
                y.write(money(r["cost"]))
                if z.button("Quitar", key=f"remove_{i}"):
                    st.session_state.quote.pop(i)
                    st.rerun()
        default_labor = calculate(st.session_state.quote)[2]
        if st.session_state.get("labor_override", 0) == 0:
            st.session_state.labor_override = int(default_labor)
        st.number_input("Mano de obra", min_value=0, step=1000, key="labor_override", help="Ajustable para esta cotización.")
        parts, logistics, labor, base, pmin, prec, pprem = calculate(st.session_state.quote)
        a, b, c = st.columns(3)
        a.metric("Repuestos", money(parts)); b.metric("Logística", money(logistics)); c.metric("Mano de obra", money(labor))
        st.markdown(f'<div class="big-result"><div class="label">COSTO REAL DE LA REPARACIÓN</div><div class="value">{money(base)}</div></div>', unsafe_allow_html=True)
        a, b, c = st.columns(3)
        a.metric("Mínimo", money(pmin)); b.metric("RECOMENDADO", money(prec)); c.metric("Premium", money(pprem))
        a, b = st.columns(2)
        if a.button("Guardar cotización", type="primary", use_container_width=True):
            cdb = db()
            payload = {"items": st.session_state.quote, "parts": parts, "logistics": logistics, "labor": labor, "base": base, "recommended": prec}
            cdb.execute("INSERT INTO history(created_at,data) VALUES(?,?)", (datetime.now().isoformat(timespec="seconds"), json.dumps(payload, ensure_ascii=False)))
            cdb.commit(); cdb.close(); st.success("Cotización guardada.")
        if b.button("Limpiar cotización", use_container_width=True):
            reset_quote(); st.rerun()
    elif allrefs:
        st.info("Selecciona una referencia y agrégala al cálculo. Puedes agregar varias reparaciones.")

elif page == "Referencias":
    st.header("Referencias")
    st.caption("Catálogo de repuestos por modelo, variante y proveedor. También puedes actualizarlo desde el PDF.")
    ps = list(providers())
    provider_names = [p["name"] for p in ps]
    markboss = next((p for p in ps if p["name"].lower() == "markboss repuestos".lower()), ps[0] if ps else None)

    st.markdown('<div class="import-card"><b>📄 Importar catálogo de MarkBoss</b><br>Sube el PDF de precios. El sistema reconocerá marca, modelo, variante y precio; si ya existe una referencia, actualizará su precio en vez de duplicarla.</div>', unsafe_allow_html=True)
    if not ps:
        st.error("Primero debes crear al menos un proveedor.")
    else:
        up = st.file_uploader("PDF de precios", type=["pdf"], key="markboss_pdf")
        if up is not None:
            if st.button("Analizar PDF", type="primary", use_container_width=True):
                try:
                    parsed, skipped = parse_markboss_pdf(up)
                    st.session_state["parsed_pdf_rows"] = parsed
                    st.session_state["parsed_pdf_skipped"] = skipped
                    st.success(f"Se encontraron {len(parsed)} referencias con precio.")
                except Exception as e:
                    st.error(f"No se pudo analizar el PDF: {e}")
        parsed = st.session_state.get("parsed_pdf_rows", [])
        if parsed:
            st.write(f"**Vista previa:** {len(parsed)} referencias listas para importar · {st.session_state.get('parsed_pdf_skipped', 0)} líneas sin precio/no reconocidas.")
            st.dataframe(parsed[:100], use_container_width=True, hide_index=True)
            chosen_provider = st.selectbox("Guardar como proveedor", provider_names, index=provider_names.index(markboss["name"]) if markboss and markboss["name"] in provider_names else 0)
            chosen_id = next(p["id"] for p in ps if p["name"] == chosen_provider)
            if st.button("⬇️ Importar / actualizar referencias", type="primary", use_container_width=True):
                ins, upd = import_rows(parsed, chosen_id)
                st.session_state.pop("parsed_pdf_rows", None)
                st.success(f"Importación terminada: {ins} nuevas · {upd} actualizadas · sin duplicados por marca/modelo/variante/proveedor.")
                st.rerun()

    st.divider()
    st.subheader("Agregar o actualizar manualmente")
    if ps:
        brands_existing = sorted({r["brand"] for r in refs()})
        brand_choice = st.selectbox("Marca", ["＋ Nueva marca..."] + brands_existing, key="ref_brand_choice")
        brand_manual = st.text_input("Nueva marca", key="ref_brand_manual") if brand_choice.startswith("＋") else brand_choice
        models_existing = sorted({r["model"] for r in refs() if r["brand"] == brand_manual})
        model_choice = st.selectbox("Modelo", ["＋ Nuevo modelo..."] + models_existing, key="ref_model_choice")
        model_manual = st.text_input("Nuevo modelo", key="ref_model_manual") if model_choice.startswith("＋") else model_choice
        a, b = st.columns(2)
        repair = a.selectbox("Tipo de reparación", REPAIRS, key="ref_repair")
        quality = b.text_input("Variante / calidad", placeholder="OLED, INCELL, C/M, GX, JK...", key="ref_quality")
        a, b = st.columns(2)
        provider_name = a.selectbox("Proveedor", provider_names, key="ref_provider")
        cost = b.number_input("Costo del repuesto", min_value=0, step=1000, key="ref_cost")
        note = st.text_area("Nota", key="ref_note")
        if st.button("Guardar referencia", type="primary", use_container_width=True):
            bc = normalize_text(brand_manual).upper(); mc = normalize_text(model_manual).upper(); qc = normalize_text(quality).upper()
            if not bc or not mc or cost <= 0:
                st.error("Marca, modelo y costo son obligatorios.")
            else:
                pid = next(p["id"] for p in ps if p["name"] == provider_name)
                c = db()
                existing = c.execute("SELECT id FROM references_ WHERE lower(brand)=lower(?) AND lower(model)=lower(?) AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?", (bc, mc, repair, qc, pid)).fetchone()
                if existing:
                    c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?", (cost, note.strip(), existing["id"])); msg = "Referencia existente actualizada."
                else:
                    c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)", (bc, mc, repair, qc, pid, cost, note.strip())); msg = "Referencia guardada."
                c.commit(); c.close(); st.success(msg); st.rerun()

    q = st.text_input("Buscar referencias", placeholder="Ej. IPHONE 13, OLED, MARCO...")
    data = [x for x in refs() if q.strip().lower() in " ".join(str(x[k] or "") for k in ["brand", "model", "repair", "quality", "provider"]).lower()]
    st.caption(f"{len(data)} referencia(s) encontrada(s).")
    for r in data:
        with st.expander(f"{r['brand']} · {r['model']} · {r['quality'] or 'Sin variante'} · {r['provider']}"):
            st.write(f"**Tipo:** {r['repair']} · **Costo:** {money(r['cost'])}")
            st.caption(r["note"] or "Sin nota")

elif page == "Proveedores":
    st.header("Proveedores")
    st.caption("Define cómo recibes el repuesto y los costos de logística.")
    for p in providers():
        with st.expander(p["name"]):
            with st.form(f"p{p['id']}"):
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
            if not name.strip(): st.error("Escribe el nombre del proveedor.")
            else:
                c = db(); c.execute("INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)", (name.strip(), delivery, shipping, travel, note)); c.commit(); c.close(); st.rerun()

elif page == "Configuración":
    st.header("Configuración")
    s = settings()
    st.subheader("Mano de obra por reparación")
    with st.form("labor"):
        vals = {k: st.number_input(k, min_value=0, step=1000, value=int(s.get(f"labor_{k}", v))) for k, v in DEFAULT_LABOR.items()}
        bundle = st.number_input("Mano de obra combinada", min_value=0, step=1000, value=int(s.get("bundle_labor", 75000)))
        if st.form_submit_button("Guardar mano de obra", type="primary"):
            for k, v in vals.items(): save_setting(f"labor_{k}", v)
            save_setting("bundle_labor", bundle); st.rerun()
    st.subheader("Márgenes")
    with st.form("margins"):
        a, b, c = st.columns(3)
        mi = a.number_input("Mínimo %", min_value=0, value=int(s["margin_min"]))
        mr = b.number_input("Recomendado %", min_value=0, value=int(s["margin_rec"]))
        mp = c.number_input("Premium %", min_value=0, value=int(s["margin_prem"]))
        rnd = st.number_input("Redondear a", min_value=1, step=100, value=int(s["rounding"]))
        if st.form_submit_button("Guardar márgenes"):
            save_setting("margin_min", mi); save_setting("margin_rec", mr); save_setting("margin_prem", mp); save_setting("rounding", rnd); st.rerun()
    backup = {"providers": [dict(x) for x in providers()], "references": [dict(x) for x in refs()], "settings": settings()}
    st.download_button("Descargar respaldo JSON", json.dumps(backup, ensure_ascii=False, indent=2), "black-tech-cotizador.json", "application/json")

else:
    st.header("Historial")
    rows = db().execute("SELECT * FROM history ORDER BY id DESC LIMIT 100").fetchall()
    if not rows: st.info("Todavía no hay cotizaciones guardadas.")
    for h in rows:
        d = json.loads(h["data"])
        st.write(f"**{' + '.join(x['model'] for x in d['items'])}** · {' + '.join(x['repair'] for x in d['items'])} · {h['created_at']} · Recomendado: **{money(d['recommended'])}**")
