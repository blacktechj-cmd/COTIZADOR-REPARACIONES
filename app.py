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
    "Pantalla", "Batería", "Puerto de carga", "Flex de carga",
    "Flex de Encendido/Volumen", "Cámara Trasera", "Cámara Frontal",
    "Altavoz / Parlante", "Micrófono", "Placa Base (diagnóstico)",
    "IC de carga / soldadura", "Cambio de vidrio (glass)", "Sensor de huella",
    "Face ID / sensores", "Limpieza interna",
]
DEFAULT_LABOR = {
    "Pantalla": 55000, "Batería": 40000, "Puerto de carga": 60000,
    "Flex de carga": 45000, "Flex de Encendido/Volumen": 35000,
    "Cámara Trasera": 40000, "Cámara Frontal": 35000,
    "Altavoz / Parlante": 35000, "Micrófono": 35000,
    "Placa Base (diagnóstico)": 30000, "IC de carga / soldadura": 80000,
    "Cambio de vidrio (glass)": 70000, "Sensor de huella": 45000,
    "Face ID / sensores": 50000, "Limpieza interna": 30000,
}
BRANDS = ["APPLE","IPHONE","XIAOMI","SAMSUNG","MOTOROLA","HUAWEI","HONOR","OPPO","REALME","VIVO","INFINIX","TECNO","NOKIA","LG","KALLEY","GOOGLE","TCL","ZTE","ALCATEL","ASUS","ONEPLUS","SONY","LENOVO","UMIDIGI","BLU"]


def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def clean_quality(text):
    q = re.sub(r"\s+", " ", str(text or "").upper()).strip()
    q = re.sub(r"\bC\s*/\s*M\b", "CON MARCO", q)
    q = q.replace("INCELLL", "INCELL")
    return q or "ESTÁNDAR"


def screen_quality_from_text(text):
    up = str(text or "").upper()
    tokens = []
    for token in ["SOFT OLED", "INCELL", "OLED", "ORIGINAL", "GX", "JK", "CON MARCO", "C/M", "LCD"]:
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", up):
            tokens.append("CON MARCO" if token == "C/M" else token)
    return clean_quality(" ".join(tokens))


def normalize_screen_model(model):
    return re.sub(r"\s+", " ", str(model or "")).strip(" -/").title()


def migrate_catalog(c):
    rows = c.execute("SELECT id,repair,quality FROM references_").fetchall()
    for r in rows:
        repair = str(r["repair"] or "").strip()
        quality = clean_quality(r["quality"])
        up = f"{repair} {quality}".upper()
        if any(x in up for x in ["DISPLAY", "PANTALLA", "LCD", "OLED", "INCELL", "GX", "JK"]):
            if repair.upper() in ("PANTALLA LCD", "DISPLAY LCD") and "LCD" not in quality:
                quality = clean_quality("LCD " + quality)
            if repair.upper() in ("PANTALLA OLED", "DISPLAY OLED") and "OLED" not in quality:
                quality = clean_quality("OLED " + quality)
            c.execute("UPDATE references_ SET repair='Pantalla',quality=? WHERE id=?", (quality, r["id"]))
    dupes = c.execute("""
        SELECT lower(brand) b, lower(model) m, lower(repair) r, lower(quality) q, provider_id,
               MAX(id) keep_id, GROUP_CONCAT(id) ids
        FROM references_
        GROUP BY lower(brand),lower(model),lower(repair),lower(quality),provider_id
        HAVING COUNT(*) > 1
    """).fetchall()
    for d in dupes:
        for old_id in [int(x) for x in d["ids"].split(",") if int(x) != d["keep_id"]]:
            c.execute("DELETE FROM references_ WHERE id=?", (old_id,))


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS providers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,delivery TEXT NOT NULL DEFAULT 'Envío',shipping INTEGER NOT NULL DEFAULT 0,travel INTEGER NOT NULL DEFAULT 0,note TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS references_(id INTEGER PRIMARY KEY AUTOINCREMENT,brand TEXT NOT NULL,model TEXT NOT NULL,repair TEXT NOT NULL,quality TEXT DEFAULT '',provider_id INTEGER NOT NULL,cost INTEGER NOT NULL DEFAULT 0,note TEXT DEFAULT '',FOREIGN KEY(provider_id) REFERENCES providers(id));
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,data TEXT NOT NULL);
    """)
    c.execute("INSERT OR IGNORE INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)", ("MarkBoss Repuestos","Recogida presencial",0,12000,"Catálogo PDF"))
    defaults={"margin_min":18,"margin_rec":30,"margin_prem":45,"rounding":1000,"bundle_labor":75000}
    defaults.update({f"labor_{k}":v for k,v in DEFAULT_LABOR.items()})
    for k,v in defaults.items(): c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,str(v)))
    migrate_catalog(c)
    c.commit(); c.close()


def settings(): return {r["key"]:float(r["value"]) for r in db().execute("SELECT key,value FROM settings")}
def money(v): return f"${int(round(v)):,.0f}".replace(",", ".")
def providers(): return db().execute("SELECT * FROM providers ORDER BY name").fetchall()
def refs(): return db().execute("SELECT r.*,p.name provider,p.delivery,p.shipping,p.travel FROM references_ r JOIN providers p ON p.id=r.provider_id ORDER BY lower(brand),lower(model),lower(repair),lower(quality),lower(provider)").fetchall()


def parse_pdf(pdf_bytes):
    if PdfReader is None: raise RuntimeError("Falta la dependencia pypdf.")
    reader=PdfReader(pdf_bytes); current_brand=""; rows=[]; ignored=[]
    for page_no,page in enumerate(reader.pages,1):
        for raw in (page.extract_text() or "").splitlines():
            line=re.sub(r"\s+"," ",raw).strip()
            if not line: continue
            upper=line.upper()
            if "PRECIO" in upper and not upper.startswith("DISPLAY"):
                current_brand=upper.replace("PRECIO","").strip(); continue
            if not upper.startswith("DISPLAY "): continue
            m=re.search(r"(\d{1,3}(?:[.,]\d{3})+)\s*$",line)
            if not m: ignored.append((page_no,line)); continue
            cost=int(m.group(1).replace(".","").replace(",",""))
            desc=re.sub(r"^DISPLAY\s+","",line[:m.start()].strip(),flags=re.I)
            brand=current_brand.title() if current_brand else "OTRA"
            if brand and desc.upper().startswith(brand.upper()+" "): desc=desc[len(brand):].strip()
            quality=screen_quality_from_text(desc)
            temp=desc
            for token in ["SOFT OLED","INCELLL","INCELL","CON MARCO","C/M","OLED","ORIGINAL","GX","JK","LCD"]:
                temp=re.sub(rf"(?<!\w){re.escape(token)}(?!\w)"," ",temp,flags=re.I)
            model=normalize_screen_model(temp)
            if not model: ignored.append((page_no,line)); continue
            rows.append({"brand":brand,"model":model,"repair":"Pantalla","quality":quality,"cost":cost,"page":page_no,"raw":line})
    return rows,ignored


def upsert_rows(rows,provider_name):
    c=db(); p=c.execute("SELECT id FROM providers WHERE lower(name)=lower(?)",(provider_name,)).fetchone()
    if not p:
        c.execute("INSERT INTO providers(name,delivery,note) VALUES(?,?,?)",(provider_name,"Recogida presencial","Importado automáticamente")); p=c.execute("SELECT id FROM providers WHERE lower(name)=lower(?)",(provider_name,)).fetchone()
    pid=p["id"]; added=updated=0
    for r in rows:
        q=clean_quality(r.get("quality")); exists=c.execute("SELECT id FROM references_ WHERE lower(brand)=lower(?) AND lower(model)=lower(?) AND lower(repair)=lower('Pantalla') AND lower(quality)=lower(?) AND provider_id=?",(r["brand"],r["model"],q,pid)).fetchone()
        note=f"PDF MarkBoss · página {r.get('page','')}" if r.get("page") else "Carga WhatsApp"
        if exists: c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?",(int(r["cost"]),note,exists["id"])); updated+=1
        else: c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",(r["brand"],r["model"],"Pantalla",q,pid,int(r["cost"]),note)); added+=1
    c.commit(); c.close(); return added,updated


def normalize_whatsapp_line(line):
    clean=re.sub(r"[^\w\s/+.\-$]"," ",line,flags=re.UNICODE); m=re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,6})\s*$",clean.strip())
    if not m: return None
    cost=int(m.group(1).replace(".","").replace(",","")); desc=clean[:m.start()].strip(); up=desc.upper()
    if "BATER" in up: repair="Batería"
    elif any(x in up for x in ["LCD","INCELL","DISPLAY","PANTALL","OLED","GX","JK"]): repair="Pantalla"
    else: return None
    brand=next((b.title() for b in BRANDS if re.search(rf"\b{re.escape(b)}\b",up)),"Otra")
    model=re.sub(r"\bDISPLAY\b|\bPANTALLA\b|\bBATER[IÍ]A\b"," ",desc,flags=re.I)
    for token in ["SOFT OLED","OLED","LCD","INCELL","C/M","CON MARCO","GX","JK","ORIGINAL"]: model=re.sub(rf"(?<!\w){re.escape(token)}(?!\w)"," ",model,flags=re.I)
    model=re.sub(r"\s+"," ",model).strip(" -/")
    quality=screen_quality_from_text(up) if repair=="Pantalla" else "Batería"
    return {"brand":brand,"model":model.title(),"repair":repair,"quality":quality,"cost":cost}


def calculate(items):
    s=settings(); parts=sum(int(x["cost"]) for x in items); ps={p["id"]:p for p in providers()}; logistics=0
    for pid in {x["provider_id"] for x in items}:
        p=ps[pid]; logistics += int(p["shipping"] or 0)+int(p["travel"] or 0) if p["delivery"] in ("Recogida presencial","Ambos") else int(p["shipping"] or 0)
    override=int(st.session_state.get("labor_override",0)); default=int(s.get("bundle_labor",75000)) if len(items)>1 else int(s.get(f"labor_{items[0]['repair']}",40000)) if items else 0
    labor=override or default; base=parts+logistics+labor; rnd=int(s.get("rounding",1000)) or 1; price=lambda m:round((base*(1+m/100))/rnd)*rnd
    return parts,logistics,labor,base,price(s["margin_min"]),price(s["margin_rec"]),price(s["margin_prem"])


def add_quote(r):
    if r["id"] not in [x["id"] for x in st.session_state.quote]: st.session_state.quote.append(dict(r))
def reset_quote(): st.session_state.quote=[]; st.session_state.labor_override=0

st.set_page_config(page_title="BLACK TECH · Cotizador",page_icon="💰",layout="wide",initial_sidebar_state="collapsed")
init_db()
if "quote" not in st.session_state: st.session_state.quote=[]
if "labor_override" not in st.session_state: st.session_state.labor_override=0

st.markdown("""
<style>
.block-container{max-width:1180px;padding:1rem 1rem 4rem}.hero{background:linear-gradient(135deg,#0f172a,#1e293b 62%,#2563eb);color:#fff;padding:20px 22px;border-radius:20px;margin-bottom:14px;box-shadow:0 8px 28px rgba(15,23,42,.14)}.hero h1{margin:0;font-size:1.9rem;letter-spacing:.08em}.hero p{margin:4px 0 0;color:#cbd5e1}.navbox{background:#f8fafc;border:1px solid #e2e8f0;padding:10px 12px;border-radius:16px;margin-bottom:18px}.big-result{background:linear-gradient(135deg,#eff6ff,#fff);border:2px solid #2563eb;border-radius:18px;padding:18px;text-align:center;margin:14px 0}.big-result .value{font-size:2.25rem;font-weight:800;color:#1d4ed8}.big-result .label{color:#64748b;font-size:.88rem}
</style>
""",unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>BLACK TECH</h1><p>Cotizador profesional de reparaciones</p></div>',unsafe_allow_html=True)

pages=["💰 Cotizar","📚 Referencias","📄 Catálogo PDF","📱 WhatsApp","🚚 Proveedores","⚙️ Configuración","🧾 Historial"]
st.markdown('<div class="navbox">',unsafe_allow_html=True); page=st.selectbox("Módulo",pages,label_visibility="collapsed"); st.markdown('</div>',unsafe_allow_html=True)
allrefs=list(refs())

if page=="💰 Cotizar":
    st.header("Nueva cotización"); st.caption("Marca y modelo son listas dependientes; el tipo de reparación controla qué repuestos aparecen.")
    brands=sorted(set(r["brand"] for r in allrefs),key=str.lower); a,b=st.columns(2)
    brand=a.selectbox("Marca",[""]+brands,format_func=lambda x:"Selecciona una marca..." if not x else x,key="q_brand")
    models=sorted(set(r["model"] for r in allrefs if not brand or r["brand"].lower()==brand.lower()),key=str.lower)
    model=b.selectbox("Modelo",[""]+models,format_func=lambda x:"Selecciona un modelo..." if not x else x,key="q_model")
    available=[r for r in allrefs if (not brand or r["brand"].lower()==brand.lower()) and (not model or r["model"].lower()==model.lower())]
    repair_options=[""]+sorted(set(r["repair"] for r in available),key=str.lower)
    repair=st.selectbox("Tipo de reparación",repair_options,format_func=lambda x:"Selecciona el tipo de reparación..." if not x else x,key="q_repair")
    matches=[r for r in available if r["repair"]==repair] if repair else []
    if matches:
        labels=[f"{r['quality'] or 'ESTÁNDAR'} · {r['provider']} · {money(r['cost'])}" for r in matches]
        idx=st.selectbox("Variante / calidad / proveedor",range(len(matches)),format_func=lambda i:labels[i],key="q_ref"); selected=matches[idx]
        st.info(f"{selected['brand']} {selected['model']} · {selected['quality'] or 'ESTÁNDAR'} · {selected['provider']} · {money(selected['cost'])}")
        if st.button("＋ Agregar reparación al cálculo",type="primary",use_container_width=True): add_quote(selected); st.rerun()
    elif repair: st.warning("No hay repuestos disponibles para esta reparación en ese modelo.")
    if st.session_state.quote:
        st.divider(); st.subheader("Reparaciones agregadas")
        for i,r in enumerate(st.session_state.quote):
            with st.container(border=True):
                x,y,z=st.columns([5,2,1]); x.write(f"**{r['repair']} · {r['quality'] or 'ESTÁNDAR'}**"); x.caption(f"{r['brand']} {r['model']} · {r['provider']}"); y.write(money(r['cost']))
                if z.button("Quitar",key=f"remove_{i}"): st.session_state.quote.pop(i); st.rerun()
        default_labor=calculate(st.session_state.quote)[2]
        if st.session_state.get("labor_override",0)==0: st.session_state.labor_override=int(default_labor)
        st.number_input("Mano de obra",min_value=0,step=1000,key="labor_override")
        parts,logistics,labor,base,pmin,prec,pprem=calculate(st.session_state.quote); a,b,c=st.columns(3)
        a.metric("Repuestos",money(parts)); b.metric("Logística",money(logistics)); c.metric("Mano de obra",money(labor))
        st.markdown(f'<div class="big-result"><div class="label">COSTO REAL</div><div class="value">{money(base)}</div></div>',unsafe_allow_html=True)
        a,b,c=st.columns(3); a.metric("Mínimo",money(pmin)); b.metric("RECOMENDADO",money(prec)); c.metric("Premium",money(pprem)); a,b=st.columns(2)
        if a.button("Guardar cotización",type="primary",use_container_width=True):
            payload={"items":st.session_state.quote,"parts":parts,"logistics":logistics,"labor":labor,"base":base,"recommended":prec}; cdb=db(); cdb.execute("INSERT INTO history(created_at,data) VALUES(?,?)",(datetime.now().isoformat(timespec="seconds"),json.dumps(payload,ensure_ascii=False))); cdb.commit(); cdb.close(); st.success("Cotización guardada.")
        if b.button("Limpiar cotización",use_container_width=True): reset_quote(); st.rerun()
    else: st.info("Selecciona un repuesto y agrégalo al cálculo.")

elif page=="📚 Referencias":
    st.header("Catálogo de referencias"); st.caption("Pantalla es la reparación. LCD, OLED, GX, JK y CON MARCO son variantes.")
    ps=list(providers()); provider_names=[p["name"] for p in ps]
    if ps:
        with st.form("new_ref"):
            brands_existing=sorted(set(r["brand"] for r in allrefs),key=str.lower); brand=st.selectbox("Marca",["＋ Nueva marca..."]+brands_existing,key="r_brand"); brand_manual=st.text_input("Nueva marca") if brand.startswith("＋") else brand
            models_existing=sorted(set(r["model"] for r in allrefs if r["brand"].lower()==brand_manual.lower()),key=str.lower); model=st.selectbox("Modelo",["＋ Nuevo modelo..."]+models_existing,key="r_model"); model_manual=st.text_input("Nuevo modelo") if model.startswith("＋") else model
            a,b=st.columns(2); repair=a.selectbox("Tipo de reparación",REPAIRS,key="r_repair"); quality=b.text_input("Variante / calidad",placeholder="OLED, INCELL, CON MARCO, GX, JK")
            a,b=st.columns(2); provider_name=a.selectbox("Proveedor",provider_names); cost=b.number_input("Costo",min_value=0,step=1000); note=st.text_area("Nota")
            if st.form_submit_button("Guardar / actualizar referencia",type="primary",use_container_width=True):
                bc=(brand_manual if brand.startswith("＋") else brand).strip().upper(); mc=(model_manual if model.startswith("＋") else model).strip().upper(); qc=clean_quality(quality)
                if not bc or not mc or cost<=0: st.error("Marca, modelo y costo son obligatorios.")
                else:
                    pid=next(p["id"] for p in ps if p["name"]==provider_name); c=db(); existing=c.execute("SELECT id FROM references_ WHERE lower(brand)=lower(?) AND lower(model)=lower(?) AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?",(bc,mc,repair,qc,pid)).fetchone()
                    if existing: c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?",(cost,note.strip(),existing["id"]))
                    else: c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",(bc,mc,repair,qc,pid,cost,note.strip()))
                    c.commit(); c.close(); st.success("Referencia guardada."); st.rerun()
    q=st.text_input("Buscar referencias",placeholder="Ej. IPHONE 13, OLED, CON MARCO..."); data=[x for x in refs() if q.strip().lower() in " ".join(str(x[k] or "") for k in ["brand","model","repair","quality","provider"]).lower()]
    st.caption(f"{len(data)} referencia(s) encontrada(s).")
    for r in data:
        with st.expander(f"{r['brand']} · {r['model']} · {r['quality'] or 'ESTÁNDAR'} · {r['provider']}"): st.write(f"**Tipo:** {r['repair']} · **Costo:** {money(r['cost'])}"); st.caption(r["note"] or "Sin nota")

elif page=="📄 Catálogo PDF":
    st.header("Importar catálogo de MarkBoss"); st.caption("El PDF se transforma a Marca → Modelo → Pantalla → Variante → Precio. Las filas sin precio se omiten.")
    uploaded=st.file_uploader("PDF de precios",type=["pdf"],key="pdf_upload")
    if uploaded:
        if st.button("Analizar PDF",type="primary",use_container_width=True):
            try:
                rows,ignored=parse_pdf(uploaded.getvalue()); st.session_state.pdf_rows=rows; st.session_state.pdf_ignored=ignored; st.success(f"Encontradas {len(rows)} referencias con precio. {len(ignored)} líneas sin precio fueron omitidas.")
            except Exception as e: st.error(f"No se pudo analizar el PDF: {e}")
        rows=st.session_state.get("pdf_rows",[])
        if rows:
            st.dataframe([{"Marca":r["brand"],"Modelo":r["model"],"Tipo":"Pantalla","Variante":r["quality"],"Precio":money(r["cost"]),"Página":r["page"]} for r in rows],use_container_width=True,hide_index=True)
            if st.button("Importar / actualizar catálogo MarkBoss",type="primary",use_container_width=True):
                a,u=upsert_rows(rows,"MarkBoss Repuestos"); st.success(f"Catálogo actualizado: {a} nuevas · {u} actualizadas."); st.session_state.pdf_rows=[]; st.rerun()

elif page=="📱 WhatsApp":
    st.header("Carga rápida por WhatsApp"); st.caption("Pega las líneas del proveedor que te cotiza por WhatsApp y guárdalas para reutilizarlas.")
    ps=list(providers()); provider_names=[p["name"] for p in ps]; provider_name=st.selectbox("Proveedor",provider_names if provider_names else ["Crear proveedor primero"])
    text=st.text_area("Lista de WhatsApp",height=240,placeholder="Ejemplo:\nXiaomi Redmi 13 INCELL 42.000\nXiaomi Redmi 13 OLED C/M 65.000")
    if st.button("Analizar lista",type="primary",use_container_width=True):
        parsed=[normalize_whatsapp_line(x) for x in text.splitlines()]; parsed=[x for x in parsed if x]; st.session_state.wa_rows=parsed; st.success(f"Se reconocieron {len(parsed)} líneas.")
    rows=st.session_state.get("wa_rows",[])
    if rows:
        st.dataframe([{"Marca":r["brand"],"Modelo":r["model"],"Tipo":r["repair"],"Variante":r["quality"],"Costo":money(r["cost"])} for r in rows],use_container_width=True,hide_index=True)
        if st.button("Guardar / actualizar referencias",type="primary",use_container_width=True):
            a,u=upsert_rows(rows,provider_name); st.success(f"Guardado: {a} nuevas · {u} actualizadas."); st.session_state.wa_rows=[]; st.rerun()

elif page=="🚚 Proveedores":
    st.header("Proveedores")
    for p in providers():
        with st.expander(p["name"]):
            with st.form(f"provider_{p['id']}"):
                name=st.text_input("Nombre",p["name"]); delivery=st.selectbox("Entrega",["Recogida presencial","Envío","Ambos"],index=["Recogida presencial","Envío","Ambos"].index(p["delivery"])); a,b=st.columns(2); shipping=a.number_input("Envío",min_value=0,step=1000,value=int(p["shipping"])); travel=b.number_input("Desplazamiento",min_value=0,step=1000,value=int(p["travel"])); note=st.text_area("Nota",p["note"] or "")
                if st.form_submit_button("Guardar cambios",use_container_width=True):
                    c=db(); c.execute("UPDATE providers SET name=?,delivery=?,shipping=?,travel=?,note=? WHERE id=?",(name.strip(),delivery,shipping,travel,note,p["id"])); c.commit(); c.close(); st.rerun()
    st.divider()
    with st.form("new_provider"):
        name=st.text_input("Nuevo proveedor"); delivery=st.selectbox("Entrega",["Recogida presencial","Envío","Ambos"]); a,b=st.columns(2); shipping=a.number_input("Envío",min_value=0,step=1000); travel=b.number_input("Desplazamiento",min_value=0,step=1000); note=st.text_area("Nota")
        if st.form_submit_button("Agregar proveedor",use_container_width=True):
            if not name.strip(): st.error("Escribe el nombre del proveedor.")
            else:
                c=db(); c.execute("INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)",(name.strip(),delivery,shipping,travel,note)); c.commit(); c.close(); st.rerun()

elif page=="⚙️ Configuración":
    st.header("Configuración"); s=settings(); a,b,c=st.columns(3); mn=a.number_input("Margen mínimo %",value=float(s["margin_min"]),step=1.0); mr=b.number_input("Margen recomendado %",value=float(s["margin_rec"]),step=1.0); mp=c.number_input("Margen premium %",value=float(s["margin_prem"]),step=1.0); a,b=st.columns(2); rnd=a.number_input("Redondeo",min_value=1,value=int(s["rounding"]),step=1000); bundle=b.number_input("Mano de obra 2+ reparaciones",min_value=0,value=int(s["bundle_labor"]),step=1000)
    if st.button("Guardar configuración",type="primary",use_container_width=True):
        cdb=db()
        for k,v in [("margin_min",mn),("margin_rec",mr),("margin_prem",mp),("rounding",rnd),("bundle_labor",bundle)]: cdb.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
        cdb.commit(); cdb.close(); st.success("Configuración guardada.")

elif page=="🧾 Historial":
    st.header("Historial"); rows=db().execute("SELECT * FROM history ORDER BY id DESC").fetchall()
    if not rows: st.info("Todavía no hay cotizaciones guardadas.")
    for r in rows:
        data=json.loads(r["data"])
        with st.expander(f"{r['created_at']} · {money(data.get('recommended',0))}"):
            for item in data.get("items",[]): st.write(f"• {item['brand']} {item['model']} · {item['repair']} · {item['quality']} · {money(item['cost'])}")
            st.write(f"**Costo real:** {money(data.get('base',0))} · **Recomendado:** {money(data.get('recommended',0))}")
