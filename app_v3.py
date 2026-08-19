import io, json, re, sqlite3
from datetime import datetime
from pathlib import Path
import streamlit as st

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

ROOT = Path(__file__).parent
DB_PATH = ROOT / "cotizador.db"

REPAIRS = [
    "Pantalla", "Batería", "Puerto de carga", "Flex de Encendido/Volumen",
    "Cámara Trasera", "Cámara Frontal", "Altavoz / Parlante", "Micrófono",
    "Placa Base (diagnóstico)", "IC de carga / soldadura", "Cambio de vidrio (glass)",
    "Sensor de huella", "Face ID / sensores", "Limpieza interna", "Flex Carga"
]
DEFAULT_LABOR = {
    "Pantalla":55000,"Batería":40000,"Puerto de carga":60000,"Flex de Encendido/Volumen":35000,
    "Cámara Trasera":40000,"Cámara Frontal":35000,"Altavoz / Parlante":35000,"Micrófono":35000,
    "Placa Base (diagnóstico)":30000,"IC de carga / soldadura":80000,"Cambio de vidrio (glass)":70000,
    "Sensor de huella":45000,"Face ID / sensores":50000,"Limpieza interna":30000,"Flex Carga":45000
}
BRANDS=["APPLE","IPHONE","XIAOMI","SAMSUNG","MOTOROLA","HUAWEI","HONOR","OPPO","REALME","VIVO","INFINIX","TECNO","NOKIA","LG","KALLEY","GOOGLE","TCL","ZTE","ALCATEL","ASUS","ONEPLUS","SONY","LENOVO","UMIDIGI","BLU"]


def db():
    c=sqlite3.connect(DB_PATH,check_same_thread=False)
    c.row_factory=sqlite3.Row
    return c

def money(v): return f"${int(round(float(v or 0))):,.0f}".replace(",",".")
def norm(s): return re.sub(r"\s+"," ",str(s or "")).strip()

def canonical_brand(s):
    u=norm(s).upper()
    if u in ("IPHONE","I PHONE"): return "Apple"
    for b in BRANDS:
        if re.search(rf"(?<!\w){re.escape(b)}(?!\w)",u): return b.title()
    return norm(s).title() or "Otra"

def canonical_model(s):
    m=norm(s).upper()
    # A30/50 -> A30/A50; A30 / 50 -> A30/A50; A30/A50 remains A30/A50
    m=re.sub(r"\b([A-Z]{1,4}\d{1,4})\s*/\s*(\d{1,4})\b",lambda x:f"{x.group(1)}/{x.group(1)[:re.search(r'\d',x.group(1)).start()]}{x.group(2)}",m)
    m=re.sub(r"\b([A-Z]{1,4}\d{1,4})\s*/\s*([A-Z])?(\d{1,4})\b",lambda x:f"{x.group(1)}/{x.group(2) or x.group(1)[0]}{x.group(3)}",m)
    return norm(m).title()

def quality(s):
    q=norm(s).upper().replace("INCELLL","INCELL")
    q=re.sub(r"\bC\s*/\s*M\b","CON MARCO",q)
    if "INCELL" in q:
        q=re.sub(r"\bLCD\s+INCELL\b","INCELL",q)
        q=re.sub(r"\bINCELL\s+LCD\b","INCELL",q)
    return norm(q) or "INCELL"

def screen_quality(s):
    u=str(s or "").upper(); found=[]
    for t in ["SOFT OLED","INCELL","OLED","LCD","ORIGINAL","GX","JK","CON MARCO","C/M"]:
        if re.search(rf"(?<!\w){re.escape(t)}(?!\w)",u): found.append("CON MARCO" if t=="C/M" else t)
    return quality(" ".join(found)) if found else "INCELL"

def init_db():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS providers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,delivery TEXT NOT NULL DEFAULT 'Envío',shipping INTEGER NOT NULL DEFAULT 0,travel INTEGER NOT NULL DEFAULT 0,note TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS references_(id INTEGER PRIMARY KEY AUTOINCREMENT,brand TEXT NOT NULL,model TEXT NOT NULL,repair TEXT NOT NULL,quality TEXT DEFAULT '',provider_id INTEGER NOT NULL,cost INTEGER NOT NULL DEFAULT 0,note TEXT DEFAULT '',FOREIGN KEY(provider_id) REFERENCES providers(id));
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,data TEXT NOT NULL);
    ''')
    c.execute("INSERT OR IGNORE INTO providers(name,delivery,travel,note) VALUES(?,?,?,?)",("MarkBoss Repuestos","Recogida presencial",12000,"Catálogo PDF"))
    defaults={"margin_min":18,"margin_rec":30,"margin_prem":45,"rounding":1000,"bundle_labor":75000}
    defaults.update({f"labor_{k}":v for k,v in DEFAULT_LABOR.items()})
    for k,v in defaults.items(): c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,str(v)))
    # Canonicalize existing records and remove exact duplicates without deleting distinct providers/variants.
    rows=c.execute("SELECT id,brand,model,repair,quality FROM references_").fetchall()
    for r in rows:
        rep="Pantalla" if r["repair"].upper() in ("DISPLAY","PANTALLA","DISPLAY LCD","DISPLAY OLED","PANTALLA LCD","PANTALLA OLED") else r["repair"]
        q=screen_quality(("LCD " if r["repair"].upper() in ("DISPLAY LCD","PANTALLA LCD") else "OLED " if r["repair"].upper() in ("DISPLAY OLED","PANTALLA OLED") else "")+str(r["quality"] or "")) if rep=="Pantalla" else quality(r["quality"])
        c.execute("UPDATE references_ SET brand=?,model=?,repair=?,quality=? WHERE id=?",(canonical_brand(r["brand"]),canonical_model(r["model"]),rep,q,r["id"]))
    c.commit()
    # Deduplicate after canonicalization, keeping the newest row for the same provider.
    d=c.execute('''SELECT lower(brand) b,lower(model) m,lower(repair) r,lower(quality) q,provider_id,GROUP_CONCAT(id) ids,MAX(id) keep_id FROM references_ GROUP BY b,m,r,q,provider_id HAVING COUNT(*)>1''').fetchall()
    for x in d:
        ids=[int(i) for i in x["ids"].split(",")]
        for i in ids:
            if i!=x["keep_id"]: c.execute("DELETE FROM references_ WHERE id=?",(i,))
    c.commit(); c.close()

def providers(): return db().execute("SELECT * FROM providers ORDER BY lower(name)").fetchall()
def refs(): return db().execute("SELECT r.*,p.name provider,p.delivery,p.shipping,p.travel FROM references_ r JOIN providers p ON p.id=r.provider_id ORDER BY lower(brand),lower(model),lower(repair),lower(quality),lower(provider)").fetchall()
def settings(): return {r["key"]:float(r["value"]) for r in db().execute("SELECT key,value FROM settings")}

def upsert(brand,model,repair,q,pid,cost,note=""):
    brand=canonical_brand(brand); model=canonical_model(model); q=screen_quality(q) if repair=="Pantalla" else quality(q)
    c=db(); old=c.execute("SELECT id FROM references_ WHERE lower(brand)=lower(?) AND lower(model)=lower(?) AND lower(repair)=lower(?) AND lower(quality)=lower(?) AND provider_id=?",(brand,model,repair,q,pid)).fetchone()
    if old: c.execute("UPDATE references_ SET cost=?,note=? WHERE id=?",(int(cost),note,old["id"])); action="actualizada"
    else: c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",(brand,model,repair,q,pid,int(cost),note)); action="nueva"
    c.commit(); c.close(); return action

def provider_id(name):
    p=next((p for p in providers() if p["name"].lower()==name.lower()),None)
    if p:return p["id"]
    c=db(); c.execute("INSERT INTO providers(name,delivery,note) VALUES(?,?,?)",(name,"Envío","Importado automáticamente")); c.commit(); pid=c.execute("SELECT id FROM providers WHERE name=?",(name,)).fetchone()[0]; c.close(); return pid

def parse_price(line):
    m=re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,6})\s*$",line.strip())
    return (None,line.strip()) if not m else (int(m.group(1).replace('.','').replace(',','')),line[:m.start()].strip())

def parse_pdf(data):
    if PdfReader is None: raise RuntimeError("Falta pypdf en requirements.txt")
    reader=PdfReader(io.BytesIO(data)); brand=""; rows=[]; ignored=[]
    for pg,page in enumerate(reader.pages,1):
        for raw in (page.extract_text() or "").splitlines():
            line=norm(raw); u=line.upper()
            if not line: continue
            if "PRECIO" in u and not re.match(r"^D?DISPLAY\b|^BATER[IÍ]A\b",u):
                h=re.sub(r"\bPRECIO\b","",u).strip()
                if h: brand=canonical_brand(h)
                continue
            display=bool(re.match(r"^D?DISPLAY\b",u)); battery=bool(re.match(r"^BATER[IÍ]A\b",u))
            if not(display or battery): continue
            cost,desc=parse_price(line)
            if cost is None: ignored.append((pg,line)); continue
            if display:
                desc=re.sub(r"^D?DISPLAY\s+","",desc,flags=re.I); rep="Pantalla"; q=screen_quality(desc); model=desc
                for t in ["SOFT OLED","INCELLL","INCELL","CON MARCO","C/M","OLED","ORIGINAL","GX","JK","LCD"]: model=re.sub(rf"(?<!\w){re.escape(t)}(?!\w)"," ",model,flags=re.I)
            else:
                desc=re.sub(r"^BATER[IÍ]A\s+","",desc,flags=re.I); rep="Batería"; q="INCELL"; model=desc
            model=canonical_model(model.strip(" -/")); b=brand or canonical_brand(desc)
            if model.upper().startswith(b.upper()+" "): model=model[len(b):].strip()
            if model: rows.append({"brand":b,"model":model,"repair":rep,"quality":q,"cost":cost,"page":pg})
    return rows,ignored

def import_rows(rows,pname):
    pid=provider_id(pname); a=u=0
    for r in rows:
        if upsert(r["brand"],r["model"],r["repair"],r["quality"],pid,r["cost"],f"PDF/WhatsApp · página {r.get('page','')}")=="nueva":a+=1
        else:u+=1
    return a,u

def parse_wa(line):
    clean=re.sub(r"[^\w\s/+.\-$]"," ",line,flags=re.UNICODE); cost,desc=parse_price(clean)
    if cost is None:return None
    u=desc.upper(); rep="Batería" if "BATER" in u else "Pantalla" if any(x in u for x in ["LCD","INCELL","DISPLAY","PANTALL","OLED","GX","JK"]) else None
    if not rep:return None
    b=canonical_brand(desc); model=re.sub(r"\bDISPLAY\b|\bPANTALLA\b|\bBATER[IÍ]A\b"," ",desc,flags=re.I)
    for t in ["SOFT OLED","OLED","LCD","INCELL","C/M","CON MARCO","GX","JK","ORIGINAL"]: model=re.sub(rf"(?<!\w){re.escape(t)}(?!\w)"," ",model,flags=re.I)
    return {"brand":b,"model":canonical_model(model),"repair":rep,"quality":screen_quality(u) if rep=="Pantalla" else "INCELL","cost":cost}

def calc(items):
    s=settings(); parts=sum(int(x["cost"]) for x in items); ps={p["id"]:p for p in providers()}; logistics=0
    for pid in {x["provider_id"] for x in items}:
        p=ps[pid]; logistics+=int(p["shipping"] or 0)+(int(p["travel"] or 0) if p["delivery"] in ("Recogida presencial","Ambos") else 0)
    labor=int(st.session_state.get("labor",0)) or int(s.get("bundle_labor",75000) if len(items)>1 else s.get(f"labor_{items[0]['repair']}",40000) if items else 0)
    base=parts+logistics+labor; rnd=int(s.get("rounding",1000)) or 1
    def price(m): return round(base*(1+m/100)/rnd)*rnd
    return parts,logistics,labor,base,price(s["margin_min"]),price(s["margin_rec"]),price(s["margin_prem"])

def dedup_group(rows):
    out={}
    for r in rows:
        key=(r["brand"].lower(),r["model"].lower(),r["repair"].lower(),r["quality"].lower(),r["provider_id"])
        out[key]=r
    return list(out.values())

init_db()
if "quote" not in st.session_state: st.session_state.quote=[]

st.set_page_config(page_title="BLACK TECH · Cotizador",page_icon="💰",layout="wide",initial_sidebar_state="collapsed")
st.markdown('''<style>
.stApp{background:#f5f7fb}.block-container{max-width:1180px;padding:.65rem .8rem 4rem}
.top{background:#fff;border:1px solid #e5e7eb;border-radius:20px;padding:12px 16px;margin-bottom:12px;box-shadow:0 7px 24px rgba(15,23,42,.06)}
.brand{display:flex;align-items:center;gap:14px}.logo{width:150px;height:74px;display:flex;align-items:center;justify-content:center}.logo b{font-size:26px;letter-spacing:.08em;line-height:.9}.logo small{display:block;font-size:8px;letter-spacing:.12em}.copy h1{margin:0;font-size:1.35rem;letter-spacing:.08em}.copy p{margin:3px 0;color:#64748b;font-size:.85rem}
div[role=radiogroup]{display:flex;gap:2px;border-bottom:1px solid #e5e7eb;overflow-x:auto;white-space:nowrap}div[role=radiogroup]>label{border-radius:0!important;border-bottom:2px solid transparent!important;background:transparent!important;padding:9px 12px!important;color:#64748b!important;font-weight:700!important;min-width:max-content}div[role=radiogroup]>label:has(input:checked){color:#111827!important;border-bottom-color:#ef4444!important}div[role=radiogroup] input{display:none}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:17px;padding:15px;margin:10px 0;box-shadow:0 5px 18px rgba(15,23,42,.035)}.brand-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;margin:9px 0;overflow:hidden}.brand-head{background:#f8fafc;border-bottom:1px solid #e5e7eb;padding:11px 14px;font-weight:850}.ref{padding:9px 14px;border-bottom:1px solid #f0f2f5}.ref:last-child{border-bottom:0}.price{font-weight:800}.hero-price{border:2px solid #2563eb;border-radius:18px;padding:16px;text-align:center;background:linear-gradient(135deg,#eff6ff,#fff)}.hero-price strong{display:block;font-size:2.1rem;color:#1d4ed8}.history{border:1px solid #e5e7eb;border-radius:16px;padding:14px;margin:9px 0;background:#fff}
@media(max-width:700px){.block-container{padding:.4rem .45rem 3rem}.logo{width:105px}.copy h1{font-size:1rem}.copy p{font-size:.72rem}div[role=radiogroup]>label{padding:8px 8px!important;font-size:.78rem!important}}
</style>''',unsafe_allow_html=True)
st.markdown('''<div class="top"><div class="brand"><div class="logo"><div><small>SERVICIO TÉCNICO</small><b>BLACK<br>TECH</b></div></div><div class="copy"><h1>BLACK TECH</h1><p>Cotizador y catálogo profesional de repuestos</p></div></div></div>''',unsafe_allow_html=True)
menu=["📥 Importar","🏆 Comparador","🧾 Venta","🧠 Catálogo maestro","💾 Datos guardados"]
page=st.radio("Módulo",menu,horizontal=True,label_visibility="collapsed",key="main_menu_v3")
allrefs=list(refs())

if page=="📥 Importar":
    st.header("Importar catálogo")
    source=st.radio("Fuente",["📄 PDF MarkBoss","📱 WhatsApp"],horizontal=True)
    if source=="📄 PDF MarkBoss":
        st.caption("Las pantallas se guardan como Pantalla + variante. Las baterías se mantienen como Batería.")
        up=st.file_uploader("PDF de precios",type=["pdf"])
        if up and st.button("Analizar PDF",type="primary",use_container_width=True):
            try:
                rows,ignored=parse_pdf(up.getvalue()); st.session_state.pdf_rows=rows
                st.success(f"Encontradas {len(rows)} referencias: {sum(r['repair']=='Pantalla' for r in rows)} pantallas y {sum(r['repair']=='Batería' for r in rows)} baterías.")
            except Exception as e: st.error(f"No se pudo analizar el PDF: {e}")
        rows=st.session_state.get("pdf_rows",[])
        if rows:
            st.dataframe([{"Marca":r["brand"],"Modelo":r["model"],"Tipo":r["repair"],"Variante":r["quality"],"Precio":money(r["cost"])} for r in rows],use_container_width=True,hide_index=True)
            if st.button("Guardar catálogo MarkBoss",type="primary",use_container_width=True):
                a,u=import_rows(rows,"MarkBoss Repuestos"); st.success(f"Guardado: {a} nuevas · {u} actualizadas."); st.session_state.pdf_rows=[]; st.rerun()
    else:
        ps=list(providers()); names=[p["name"] for p in ps]; pname=st.selectbox("Proveedor",names) if names else ""
        text=st.text_area("Lista de WhatsApp",height=230,placeholder="Xiaomi Redmi 13 INCELL 42.000\nSamsung A30/50 INCELL 35.000")
        if st.button("Analizar lista",type="primary",use_container_width=True): st.session_state.wa_rows=[x for x in (parse_wa(l) for l in text.splitlines()) if x]
        rows=st.session_state.get("wa_rows",[])
        if rows:
            st.dataframe([{"Marca":r["brand"],"Modelo":r["model"],"Tipo":r["repair"],"Variante":r["quality"],"Costo":money(r["cost"])} for r in rows],use_container_width=True,hide_index=True)
            if st.button("Guardar / actualizar",type="primary",use_container_width=True):
                a,u=import_rows(rows,pname); st.success(f"Guardado: {a} nuevas · {u} actualizadas."); st.session_state.wa_rows=[]; st.rerun()

elif page=="🏆 Comparador":
    st.header("Comparador y cotizador")
    brands=sorted(set(r["brand"] for r in allrefs),key=str.lower); a,b=st.columns(2)
    brand=a.selectbox("Marca",[""]+brands,format_func=lambda x:"Selecciona una marca..." if not x else x)
    models=sorted(set(r["model"] for r in allrefs if not brand or r["brand"].lower()==brand.lower()),key=str.lower)
    model=b.selectbox("Modelo",[""]+models,format_func=lambda x:"Selecciona un modelo..." if not x else x)
    available=[r for r in allrefs if (not brand or r["brand"].lower()==brand.lower()) and (not model or r["model"].lower()==model.lower())]
    repair=st.selectbox("Tipo de reparación",[""]+REPAIRS,format_func=lambda x:"Selecciona el tipo de reparación..." if not x else x)
    matches=[r for r in available if r["repair"].lower()==repair.lower()] if repair else []
    if matches:
        st.markdown('<div class="card"><b>Referencias disponibles</b></div>',unsafe_allow_html=True)
        labels=[f"{r['quality']} · {r['provider']} · {money(r['cost'])}" for r in matches]
        chosen=st.selectbox("Referencia",range(len(matches)),format_func=lambda i:labels[i])
        if st.button("＋ Agregar reparación al cálculo",type="primary",use_container_width=True):
            r=dict(matches[chosen])
            if r["id"] not in [x["id"] for x in st.session_state.quote]: st.session_state.quote.append(r)
            st.rerun()
    elif repair: st.info("No hay referencia registrada para este modelo y tipo de reparación.")
    if st.session_state.quote:
        st.subheader("Reparaciones agregadas")
        for i,r in enumerate(st.session_state.quote):
            with st.container(border=True):
                a,b,c=st.columns([5,2,1]); a.write(f"**{r['repair']} · {r['quality']}**"); a.caption(f"{r['brand']} {r['model']} · {r['provider']}"); b.write(money(r['cost']))
                if c.button("Quitar",key=f"rm{i}"): st.session_state.quote.pop(i); st.rerun()
        st.number_input("Mano de obra",min_value=0,step=1000,key="labor")
        parts,log,labor,base,pmin,prec,pp=calc(st.session_state.quote)
        st.write(f"Repuestos: **{money(parts)}** · Logística: **{money(log)}** · Mano de obra: **{money(labor)}**")
        st.markdown(f'<div class="hero-price">COSTO REAL<strong>{money(base)}</strong></div>',unsafe_allow_html=True)
        a,b,c=st.columns(3); a.metric("Mínimo",money(pmin)); b.metric("Recomendado",money(prec)); c.metric("Premium",money(pp))
        a,b=st.columns(2)
        if a.button("Guardar cotización",type="primary",use_container_width=True):
            payload={"items":[dict(x) for x in st.session_state.quote],"parts":parts,"logistics":log,"labor":labor,"base":base,"recommended":prec,"premium":pp}
            c=db(); c.execute("INSERT INTO history(created_at,data) VALUES(?,?)",(datetime.now().isoformat(timespec="seconds"),json.dumps(payload,ensure_ascii=False))); c.commit(); c.close(); st.success("Cotización guardada en Datos guardados.")
        if b.button("Limpiar cotización",use_container_width=True): st.session_state.quote=[]; st.session_state.labor=0; st.rerun()

elif page=="🧾 Venta":
    st.header("Venta")
    q=st.text_input("Buscar equipo",placeholder="Redmi 13, A30/A50, iPhone 13...").strip().lower()
    data=[r for r in allrefs if not q or q in f"{r['brand']} {r['model']} {r['quality']}".lower()]
    for r in data:
        with st.container(border=True):
            a,b=st.columns([4,1]); a.write(f"**{r['brand']} {r['model']}**"); a.caption(f"{r['repair']} · {r['quality']} · {r['provider']}"); b.write(f"**{money(r['cost'])}**")
    if not data: st.info("No se encontraron referencias.")

elif page=="🧠 Catálogo maestro":
    st.header("Catálogo maestro")
    st.caption("Referencias agrupadas por marca y modelo. Los nombres equivalentes como A30/50 y A30/A50 se normalizan como un solo modelo.")
    grouped={}
    for r in allrefs: grouped.setdefault(r["brand"],{}).setdefault(r["model"],[]).append(r)
    for brand in sorted(grouped,key=str.lower):
        with st.expander(f"🏷️ {brand} · {len(grouped[brand])} modelo(s)"):
            for model in sorted(grouped[brand],key=str.lower):
                st.markdown(f"**{model}**")
                for r in grouped[brand][model]: st.write(f"• {r['repair']} · {r['quality']} · {r['provider']} · {money(r['cost'])}")

elif page=="💾 Datos guardados":
    st.header("Datos guardados")
    tabs=st.tabs(["Referencias","Historial","Proveedores"])
    with tabs[0]:
        q=st.text_input("Buscar referencia",placeholder="Marca, modelo, INCELL, batería...")
        data=[r for r in refs() if q.strip().lower() in " ".join(str(r[k] or '') for k in ["brand","model","repair","quality","provider"]).lower()]
        st.caption(f"{len(data)} referencia(s)")
        for r in data:
            st.markdown(f"**{r['brand']} {r['model']}** · {r['repair']} · {r['quality']} · {r['provider']} · **{money(r['cost'])}**")
    with tabs[1]:
        rows=db().execute("SELECT * FROM history ORDER BY id DESC").fetchall(); term=st.text_input("Buscar historial",key="hist_search").lower()
        for row in rows:
            d=json.loads(row["data"]); items=d.get("items",[]); equipment=f"{items[0].get('brand','')} {items[0].get('model','')}" if items else "Equipo no especificado"; repairs=", ".join(dict.fromkeys(f"{x.get('repair')} ({x.get('quality')})" for x in items))
            if term and term not in f"{equipment} {repairs}".lower(): continue
            with st.container(border=True):
                st.write(f"**📱 {equipment}** · {row['created_at']}"); st.caption(f"🛠️ {repairs}"); st.write(f"Repuestos {money(d.get('parts'))} · Costo real {money(d.get('base'))} · Recomendado {money(d.get('recommended'))}")
    with tabs[2]:
        for p in providers(): st.write(f"**{p['name']}** · {p['delivery']} · Envío {money(p['shipping'])} · Desplazamiento {money(p['travel'])}")
