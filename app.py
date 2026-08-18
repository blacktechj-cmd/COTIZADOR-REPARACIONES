import json, re, sqlite3
from datetime import datetime
from pathlib import Path
import streamlit as st

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

DB_PATH = Path(__file__).parent / "cotizador.db"

REPAIRS = [
    "Pantalla", "Pantalla LCD", "Pantalla OLED", "Batería",
    "Puerto de carga", "Flex de carga", "Flex de Encendido/Volumen",
    "Cámara Trasera", "Cámara Frontal", "Altavoz / Parlante",
    "Micrófono", "Placa Base (diagnóstico)", "IC de carga / soldadura",
    "Cambio de vidrio (glass)", "Sensor de huella", "Face ID / sensores",
    "Limpieza interna",
]
DEFAULT_LABOR = {
    "Pantalla": 55000, "Pantalla LCD": 55000, "Pantalla OLED": 65000,
    "Batería": 40000, "Puerto de carga": 60000, "Flex de carga": 45000,
    "Flex de Encendido/Volumen": 35000, "Cámara Trasera": 40000,
    "Cámara Frontal": 35000, "Altavoz / Parlante": 35000, "Micrófono": 35000,
    "Placa Base (diagnóstico)": 30000, "IC de carga / soldadura": 80000,
    "Cambio de vidrio (glass)": 70000, "Sensor de huella": 45000,
    "Face ID / sensores": 50000, "Limpieza interna": 30000,
}
BRANDS = ["APPLE","IPHONE","XIAOMI","SAMSUNG","MOTOROLA","HUAWEI","HONOR","OPPO",
          "REALME","VIVO","INFINIX","TECNO","NOKIA","LG","KALLEY","GOOGLE","TCL","ZTE",
          "ALCATEL","ASUS","ONEPLUS","SONY","LENOVO","UMIDIGI","BLU"]


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
    c.execute("""INSERT OR IGNORE INTO providers(name,delivery,shipping,travel,note)
                 VALUES(?,?,?,?,?)""",
              ("MarkBoss Repuestos","Recogida presencial",0,12000,"Catálogo PDF"))
    defaults = {"margin_min":18,"margin_rec":30,"margin_prem":45,"rounding":1000,"bundle_labor":75000}
    defaults.update({f"labor_{k}":v for k,v in DEFAULT_LABOR.items()})
    for k,v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,str(v)))
    # Migration: DISPLAY/PANTALLA imported by older versions becomes LCD or OLED.
    rows = c.execute("SELECT id,repair,quality FROM references_").fetchall()
    for r in rows:
        current = (r["repair"] or "").strip().upper()
        quality = (r["quality"] or "").strip().upper()
        if current in ("DISPLAY","PANTALLA") or current.startswith("DISPLAY "):
            new_repair = "Pantalla OLED" if "OLED" in quality else "Pantalla LCD"
            c.execute("UPDATE references_ SET repair=? WHERE id=?", (new_repair,r["id"]))
    c.commit(); c.close()


def settings():
    return {r["key"]: float(r["value"]) for r in db().execute("SELECT key,value FROM settings")}


def money(v):
    return f"${int(round(v)):,.0f}".replace(",", ".")


def providers():
    return db().execute("SELECT * FROM providers ORDER BY name").fetchall()


def refs():
    return db().execute("""
        SELECT r.*, p.name provider, p.delivery, p.shipping, p.travel
        FROM references_ r JOIN providers p ON p.id=r.provider_id
        ORDER BY lower(brand), lower(model), lower(repair), lower(quality)
    """).fetchall()


def repair_from_quality(quality):
    q = quality.upper()
    return "Pantalla OLED" if "OLED" in q else "Pantalla LCD"


def clean_quality(text):
    q = re.sub(r"\s+", " ", text.upper()).strip()
    q = re.sub(r"\bC\s*/\s*M\b", "CON MARCO", q)
    return q or "ESTÁNDAR"


def parse_pdf(pdf_bytes):
    if PdfReader is None:
        raise RuntimeError("Falta la dependencia pypdf.")
    reader = PdfReader(pdf_bytes)
    current_brand = ""
    rows, ignored = [], []
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = re.sub(r"\s+", " ", raw).strip()
            if not line:
                continue
            upper = line.upper()
            if "PRECIO" in upper and not upper.startswith("DISPLAY"):
                current_brand = upper.replace("PRECIO", "").strip()
                continue
            if not upper.startswith("DISPLAY "):
                continue
            m = re.search(r"(\d{1,3}(?:[.,]\d{3})+)\s*$", line)
            if not m:
                ignored.append((page_no,line)); continue
            cost = int(m.group(1).replace(".","").replace(",",""))
            desc = re.sub(r"^DISPLAY\s+", "", line[:m.start()].strip(), flags=re.I)
            brand = current_brand.title() if current_brand else "OTRA"
            if brand and desc.upper().startswith(brand.upper()+" "):
                desc = desc[len(brand):].strip()
            quality_tokens = ["SOFT OLED","OLED","INCELLL","INCELL","GX","JK","ORIGINAL","C/M"]
            found, temp = [], desc
            for token in quality_tokens:
                if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", temp, re.I):
                    found.append(token.replace("INCELLL","INCELL"))
                    temp = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", temp, flags=re.I)
            quality = clean_quality(" ".join(found))
            model = re.sub(r"\s+", " ", temp).strip(" -/")
            if not model:
                ignored.append((page_no,line)); continue
            rows.append({"brand":brand,"model":model.title(),"repair":repair_from_quality(quality),
                         "quality":quality,"cost":cost,"page":page_no,"raw":line})
    return rows, ignored


def upsert_rows(rows, provider_name):
    c = db()
    p = c.execute("SELECT id FROM providers WHERE lower(name)=lower(?)",(provider_name,)).fetchone()
    if not p:
        c.execute("INSERT INTO providers(name,delivery,note) VALUES(?,?,?)",
                  (provider_name,"Recogida presencial","Importado automáticamente"))
        p = c.execute("SELECT id FROM providers WHERE lower(name)=lower(?)",(provider_name,)).fetchone()
    pid = p["id"]; added = updated = 0
    for r in rows:
        q = c.execute("""SELECT id FROM references_
                         WHERE lower(brand)=lower(?) AND lower(model)=lower(?)
                         AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?""",
                      (r["brand"],r["model"],r["repair"],r["quality"],pid)).fetchone()
        note = f"PDF MarkBoss · página {r.get('page','')}" if r.get("page") else "Carga WhatsApp"
        if q:
            c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?",(r["cost"],note,q["id"]))
            updated += 1
        else:
            c.execute("""INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note)
                         VALUES(?,?,?,?,?,?,?)""",
                      (r["brand"],r["model"],r["repair"],r["quality"],pid,r["cost"],note))
            added += 1
    c.commit(); c.close()
    return added, updated


def normalize_whatsapp_line(line):
    clean = re.sub(r"[^\w\s/+.\-$]", " ", line, flags=re.UNICODE)
    m = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,6})\s*$", clean.strip())
    if not m: return None
    cost = int(m.group(1).replace(".","").replace(",",""))
    desc = clean[:m.start()].strip(); up = desc.upper()
    repair = "Batería" if "BATER" in up else ("Pantalla OLED" if "OLED" in up else ("Pantalla LCD" if any(x in up for x in ["LCD","INCELL","DISPLAY","PANTALL"]) else None))
    if not repair: return None
    brand = next((b.title() for b in BRANDS if re.search(rf"\b{re.escape(b)}\b",up)), "Otra")
    model = re.sub(r"\bDISPLAY\b|\bPANTALLA\b|\bBATER[IÍ]A\b", " ", desc, flags=re.I)
    model = re.sub(r"\b(OLED|LCD|INCELL|C/M|CON MARCO|GX|JK|ORIGINAL)\b", " ", model, flags=re.I)
    model = re.sub(r"\s+", " ", model).strip(" -/")
    quality_parts = re.findall(r"\b(SOFT OLED|OLED|LCD|INCELL|C/M|GX|JK|ORIGINAL)\b",up)
    return {"brand":brand,"model":model.title(),"repair":repair,"quality":clean_quality(" ".join(quality_parts)),"cost":cost}


def add_quote(r):
    if r["id"] not in [x["id"] for x in st.session_state.quote]:
        st.session_state.quote.append(dict(r))


def reset_quote():
    st.session_state.quote=[]; st.session_state.labor_override=0


def calculate(items):
    s=settings(); parts=sum(int(x["cost"]) for x in items)
    ps={p["id"]:p for p in providers()}; logistics=0
    for pid in {x["provider_id"] for x in items}:
        p=ps[pid]
        logistics += int(p["shipping"] or 0) + int(p["travel"] or 0) if p["delivery"] in ("Recogida presencial","Ambos") else int(p["shipping"] or 0)
    override=int(st.session_state.get("labor_override",0))
    default=int(s.get("bundle_labor",75000)) if len(items)>1 else int(s.get(f"labor_{items[0]['repair']}",40000)) if items else 0
    labor=override or default; base=parts+logistics+labor; rnd=int(s.get("rounding",1000)) or 1
    price=lambda m: round((base*(1+m/100))/rnd)*rnd
    return parts,logistics,labor,base,price(s["margin_min"]),price(s["margin_rec"]),price(s["margin_prem"])


st.set_page_config(page_title="BLACK TECH · Cotizador",page_icon="💰",layout="wide",initial_sidebar_state="collapsed")
init_db()
if "quote" not in st.session_state: st.session_state.quote=[]
if "labor_override" not in st.session_state: st.session_state.labor_override=0

st.markdown("""
<style>
.block-container{max-width:1180px;padding:1.1rem 1rem 4rem}
.hero{background:linear-gradient(135deg,#0f172a,#1e293b 60%,#2563eb);color:#fff;padding:22px 24px;border-radius:20px;margin-bottom:14px;box-shadow:0 8px 28px rgba(15,23,42,.16)}
.hero h1{margin:0;font-size:2rem;letter-spacing:.08em}.hero p{margin:4px 0 0;color:#cbd5e1}
div[role="radiogroup"]{gap:6px;flex-wrap:wrap}div[role="radiogroup"] label{border:1px solid #e2e8f0;border-radius:12px;padding:7px 13px;background:#fff}
.big-result{background:linear-gradient(135deg,#eff6ff,#fff);border:2px solid #2563eb;border-radius:18px;padding:18px;text-align:center;margin:14px 0}.big-result .value{font-size:2.25rem;font-weight:800;color:#1d4ed8}.big-result .label{color:#64748b;font-size:.88rem}
</style>
""",unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>BLACK TECH</h1><p>Cotizador profesional de reparaciones</p></div>',unsafe_allow_html=True)

pages=["Cotizar","Referencias","Importar catálogo","Proveedores","Configuración","Historial"]
page=st.radio("Navegación",pages,horizontal=True,label_visibility="collapsed")
allrefs=list(refs())

if page=="Cotizar":
    st.header("Nueva cotización")
    st.caption("Marca y modelo son listas dependientes; las variantes salen del catálogo real.")
    brands=sorted(set(r["brand"] for r in allrefs),key=str.lower)
    a,b=st.columns(2)
    brand=a.selectbox("Marca",[""]+brands,format_func=lambda x:"Selecciona una marca..." if not x else x,key="q_brand")
    models=sorted(set(r["model"] for r in allrefs if not brand or r["brand"].lower()==brand.lower()),key=str.lower)
    model=b.selectbox("Modelo",[""]+models,format_func=lambda x:"Selecciona un modelo..." if not x else x,key="q_model")
    available=[r for r in allrefs if (not brand or r["brand"].lower()==brand.lower()) and (not model or r["model"].lower()==model.lower())]
    repair_options=[""]+sorted(set(r["repair"] for r in available),key=str.lower)
    repair=st.selectbox("Tipo de reparación",repair_options,format_func=lambda x:"Selecciona el tipo de reparación..." if not x else x,key="q_repair")
    if repair=="Pantalla":
        matches=[r for r in available if r["repair"] in ("Pantalla LCD","Pantalla OLED","Pantalla")]
    else:
        matches=[r for r in available if r["repair"]==repair]
    if matches:
        labels=[f"{r['quality'] or 'ESTÁNDAR'} · {r['provider']} · {money(r['cost'])}" for r in matches]
        idx=st.selectbox("Variante / proveedor",range(len(matches)),format_func=lambda i:labels[i],key="q_ref")
        selected=matches[idx]
        st.info(f"{selected['brand']} {selected['model']} · {selected['repair']} · {selected['quality']} · {selected['provider']} · {money(selected['cost'])}")
        if st.button("＋ Agregar reparación al cálculo",type="primary",use_container_width=True): add_quote(selected); st.rerun()
    elif repair:
        st.warning("No hay referencias para esa reparación en este modelo. Revisa el catálogo importado o agrega el repuesto manualmente.")
    if st.session_state.quote:
        st.divider(); st.subheader("Reparaciones agregadas")
        for i,r in enumerate(st.session_state.quote):
            with st.container(border=True):
                x,y,z=st.columns([5,2,1]); x.write(f"**{r['repair']} · {r['quality']}**"); x.caption(f"{r['brand']} {r['model']} · {r['provider']}"); y.write(money(r['cost']))
                if z.button("Quitar",key=f"remove_{i}"): st.session_state.quote.pop(i); st.rerun()
        default_labor=calculate(st.session_state.quote)[2]
        if st.session_state.get("labor_override",0)==0: st.session_state.labor_override=int(default_labor)
        st.number_input("Mano de obra",min_value=0,step=1000,key="labor_override")
        parts,logistics,labor,base,pmin,prec,pprem=calculate(st.session_state.quote)
        a,b,c=st.columns(3); a.metric("Repuestos",money(parts)); b.metric("Logística",money(logistics)); c.metric("Mano de obra",money(labor))
        st.markdown(f'<div class="big-result"><div class="label">COSTO REAL</div><div class="value">{money(base)}</div></div>',unsafe_allow_html=True)
        a,b,c=st.columns(3); a.metric("Mínimo",money(pmin)); b.metric("RECOMENDADO",money(prec)); c.metric("Premium",money(pprem))
        st.caption("El recomendado usa el margen configurado del 30% y redondea a $1.000.")
        a,b=st.columns(2)
        if a.button("Guardar cotización",type="primary",use_container_width=True):
            cdb=db(); payload={"items":st.session_state.quote,"parts":parts,"logistics":logistics,"labor":labor,"base":base,"recommended":prec}; cdb.execute("INSERT INTO history(created_at,data) VALUES(?,?)",(datetime.now().isoformat(timespec="seconds"),json.dumps(payload,ensure_ascii=False))); cdb.commit(); cdb.close(); st.success("Cotización guardada.")
        if b.button("Limpiar cotización",use_container_width=True): reset_quote(); st.rerun()
    else: st.info("Selecciona una referencia y agrégala al cálculo.")

elif page=="Importar catálogo":
    st.header("Importar catálogo de proveedor")
    st.caption("PDF MarkBoss: actualiza precios sin duplicar. También puedes pegar una lista de WhatsApp.")
    tab1,tab2=st.tabs(["📄 PDF MarkBoss","📱 Lista WhatsApp"])
    with tab1:
        uploaded=st.file_uploader("Sube el PDF de precios",type=["pdf"],key="markboss_pdf")
        if uploaded:
            try:
                rows,ignored=parse_pdf(uploaded)
                st.success(f"Encontradas {len(rows)} referencias con precio. {len(ignored)} líneas sin precio se omitieron.")
                st.dataframe([{"Marca":r["brand"],"Modelo":r["model"],"Tipo":r["repair"],"Variante":r["quality"],"Precio":money(r["cost"]),"Página":r["page"]} for r in rows[:100]],use_container_width=True,hide_index=True)
                if st.button("Actualizar catálogo MarkBoss",type="primary",use_container_width=True):
                    added,updated=upsert_rows(rows,"MarkBoss Repuestos"); st.success(f"Catálogo actualizado: {added} nuevas y {updated} precios actualizados."); st.rerun()
            except Exception as e: st.error(f"No se pudo leer el PDF: {e}")
    with tab2:
        ps=list(providers()); provider_names=[p["name"] for p in ps]
        provider_name=st.selectbox("Proveedor",provider_names,key="wa_provider")
        text=st.text_area("Pega aquí la lista de WhatsApp",height=220,placeholder="REDMI 13 PANTALLA INCELL 42.000\nIPHONE 13 JK 79.000")
        if text.strip():
            parsed=[x for x in (normalize_whatsapp_line(line) for line in text.splitlines()) if x]
            st.write(f"Detectadas: **{len(parsed)}** líneas.")
            st.dataframe([{"Marca":x["brand"],"Modelo":x["model"],"Tipo":x["repair"],"Variante":x["quality"],"Precio":money(x["cost"])} for x in parsed],use_container_width=True,hide_index=True)
            if st.button("Guardar / actualizar lista",type="primary",use_container_width=True):
                added,updated=upsert_rows(parsed,provider_name); st.success(f"Lista actualizada: {added} nuevas y {updated} actualizadas."); st.rerun()

elif page=="Referencias":
    st.header("Referencias")
    ps=list(providers())
    if ps:
        with st.form("new_ref"):
            brands=sorted(set(r["brand"] for r in allrefs),key=str.lower)
            a,b=st.columns(2)
            brand=a.selectbox("Marca",["＋ Nueva marca"]+brands)
            new_brand=a.text_input("Nueva marca") if brand=="＋ Nueva marca" else ""
            model_options=sorted(set(r["model"] for r in allrefs if brand!="＋ Nueva marca" and r["brand"].lower()==brand.lower()),key=str.lower)
            model=b.selectbox("Modelo",["＋ Nuevo modelo"]+model_options)
            new_model=b.text_input("Nuevo modelo") if model=="＋ Nuevo modelo" else ""
            a,b=st.columns(2); repair=a.selectbox("Tipo de reparación",REPAIRS); quality=b.text_input("Variante / calidad",placeholder="INCELL CON MARCO")
            provider_name=a.selectbox("Proveedor",[p["name"] for p in ps]); cost=b.number_input("Costo",min_value=0,step=1000)
            if st.form_submit_button("Guardar referencia",type="primary",use_container_width=True):
                brand_final=(new_brand if brand=="＋ Nueva marca" else brand).strip(); model_final=(new_model if model=="＋ Nuevo modelo" else model).strip(); quality_final=clean_quality(quality)
                if not brand_final or not model_final or cost<=0: st.error("Marca, modelo y costo son obligatorios.")
                else:
                    pid=next(p["id"] for p in ps if p["name"]==provider_name); c=db()
                    exists=c.execute("""SELECT id FROM references_ WHERE lower(brand)=lower(?) AND lower(model)=lower(?) AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?""",(brand_final,model_final,repair,quality_final,pid)).fetchone()
                    if exists: c.execute("UPDATE references_ SET cost=? WHERE id=?",(cost,exists["id"]))
                    else: c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",(brand_final,model_final,repair,quality_final,pid,cost,"Carga manual"))
                    c.commit(); c.close(); st.success("Referencia guardada."); st.rerun()
    q=st.text_input("Buscar referencias"); data=[x for x in allrefs if q.strip().lower() in " ".join(str(x[k] or "") for k in ["brand","model","repair","quality","provider"]).lower()]
    st.caption(f"{len(data)} referencia(s).")
    for r in data:
        with st.expander(f"{r['brand']} · {r['model']} · {r['repair']} · {r['quality']}"):
            st.write(f"**Proveedor:** {r['provider']} · **Costo:** {money(r['cost'])}"); st.caption(r["note"] or "Sin nota")

elif page=="Proveedores":
    st.header("Proveedores")
    for p in providers():
        with st.expander(p["name"]):
            with st.form(f"provider_{p['id']}"):
                name=st.text_input("Nombre",p["name"]); delivery=st.selectbox("Entrega",["Recogida presencial","Envío","Ambos"],index=["Recogida presencial","Envío","Ambos"].index(p["delivery"]))
                a,b=st.columns(2); shipping=a.number_input("Envío",min_value=0,step=1000,value=int(p["shipping"])); travel=b.number_input("Desplazamiento",min_value=0,step=1000,value=int(p["travel"])); note=st.text_area("Nota",p["note"] or "")
                if st.form_submit_button("Guardar cambios",use_container_width=True):
                    c=db(); c.execute("UPDATE providers SET name=?,delivery=?,shipping=?,travel=?,note=? WHERE id=?",(name.strip(),delivery,shipping,travel,note,p["id"])); c.commit(); c.close(); st.rerun()
    with st.form("new_provider"):
        name=st.text_input("Nuevo proveedor"); delivery=st.selectbox("Entrega",["Recogida presencial","Envío","Ambos"]); a,b=st.columns(2); shipping=a.number_input("Envío",min_value=0,step=1000); travel=b.number_input("Desplazamiento",min_value=0,step=1000); note=st.text_area("Nota")
        if st.form_submit_button("Agregar proveedor",use_container_width=True):
            if not name.strip(): st.error("Escribe el nombre.")
            else:
                c=db(); c.execute("INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)",(name.strip(),delivery,shipping,travel,note)); c.commit(); c.close(); st.rerun()

elif page=="Configuración":
    st.header("Configuración"); s=settings()
    with st.form("settings"):
        a,b,c=st.columns(3); minm=a.number_input("Margen mínimo %",value=float(s["margin_min"]),step=1.0); rec=a.number_input("Margen recomendado %",value=float(s["margin_rec"]),step=1.0); prem=b.number_input("Margen premium %",value=float(s["margin_prem"]),step=1.0); rnd=b.number_input("Redondeo",value=int(s["rounding"]),step=1000); bundle=c.number_input("Mano de obra 2+ reparaciones",value=int(s["bundle_labor"]),step=1000)
        if st.form_submit_button("Guardar configuración",type="primary"):
            cc=db()
            for k,v in [("margin_min",minm),("margin_rec",rec),("margin_prem",prem),("rounding",rnd),("bundle_labor",bundle)]: cc.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
            cc.commit(); cc.close(); st.success("Configuración guardada.")

elif page=="Historial":
    st.header("Historial"); rows=db().execute("SELECT * FROM history ORDER BY id DESC").fetchall()
    if not rows: st.info("No hay cotizaciones guardadas.")
    for r in rows:
        data=json.loads(r["data"])
        with st.expander(f"{r['created_at']} · {money(data.get('recommended',0))} recomendado"):
            st.write(f"Costo real: **{money(data.get('base',0))}** · Repuestos: {money(data.get('parts',0))} · Mano de obra: {money(data.get('labor',0))}")
            for item in data.get("items",[]): st.write(f"- {item['brand']} {item['model']} · {item['repair']} · {item['quality']} · {money(item['cost'])}")
