import json
import sqlite3
from datetime import datetime
from pathlib import Path
import streamlit as st

DB_PATH = Path(__file__).parent / "cotizador.db"
REPAIRS = ["Pantalla OLED","Pantalla LCD","Batería","Puerto de carga","Flex de Encendido/Volumen","Cámara Trasera","Cámara Frontal","Altavoz / Parlante","Micrófono","Placa Base (diagnóstico)","IC de carga / soldadura","Cambio de vidrio (glass)","Sensor de huella","Face ID / sensores","Limpieza interna","Flex Carga"]
DEFAULT_LABOR = {"Pantalla OLED":65000,"Pantalla LCD":55000,"Batería":40000,"Puerto de carga":60000,"Flex de Encendido/Volumen":35000,"Cámara Trasera":40000,"Cámara Frontal":35000,"Altavoz / Parlante":35000,"Micrófono":35000,"Placa Base (diagnóstico)":30000,"IC de carga / soldadura":80000,"Cambio de vidrio (glass)":70000,"Sensor de huella":45000,"Face ID / sensores":50000,"Limpieza interna":30000,"Flex Carga":45000}

def db():
    c=sqlite3.connect(DB_PATH,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS providers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,delivery TEXT NOT NULL DEFAULT 'Envío',shipping INTEGER NOT NULL DEFAULT 0,travel INTEGER NOT NULL DEFAULT 0,note TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS references_(id INTEGER PRIMARY KEY AUTOINCREMENT,brand TEXT NOT NULL,model TEXT NOT NULL,repair TEXT NOT NULL,quality TEXT DEFAULT '',provider_id INTEGER NOT NULL,cost INTEGER NOT NULL DEFAULT 0,note TEXT DEFAULT '',FOREIGN KEY(provider_id) REFERENCES providers(id));
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,data TEXT NOT NULL);
    """)
    if c.execute("SELECT COUNT(*) n FROM providers").fetchone()["n"]==0:
        c.execute("INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)",("MarkBoss Repuestos","Recogida presencial",0,12000,"Desplazamiento estimado."))
    defaults={"margin_min":18,"margin_rec":30,"margin_prem":45,"rounding":1000,"bundle_labor":75000}
    defaults.update({f"labor_{k}":v for k,v in DEFAULT_LABOR.items()})
    for k,v in defaults.items(): c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,str(v)))
    p=c.execute("SELECT id FROM providers WHERE lower(name)=lower(?)",("MarkBoss Repuestos",)).fetchone()["id"]
    for repair,quality,cost in [("Pantalla LCD","LCD",35000),("Pantalla LCD","LCD con marco",38000),("Batería","Batería",25000)]:
        exists=c.execute("SELECT 1 FROM references_ WHERE lower(brand)=? AND lower(model)=? AND lower(repair)=? AND lower(quality)=? AND provider_id=?",("xiaomi","redmi 13",repair.lower(),quality.lower(),p)).fetchone()
        if not exists: c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",("Xiaomi","Redmi 13",repair,quality,p,cost,"Prueba real Redmi 13."))
    c.commit(); c.close()

def settings(): return {r["key"]:float(r["value"]) for r in db().execute("SELECT key,value FROM settings")}
def money(v): return f"${int(round(v)):,.0f}".replace(",",".")
def refs(): return db().execute("SELECT r.*,p.name provider,p.delivery,p.shipping,p.travel FROM references_ r JOIN providers p ON p.id=r.provider_id ORDER BY brand,model,repair,quality").fetchall()
def providers(): return db().execute("SELECT * FROM providers ORDER BY name").fetchall()
def save_setting(k,v):
    c=db(); c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v))); c.commit(); c.close()
def reset_quote(): st.session_state.quote=[]
def add_quote(r):
    if r["id"] not in [x["id"] for x in st.session_state.quote]: st.session_state.quote.append(dict(r))
def calculate(items):
    s=settings(); parts=sum(int(x["cost"]) for x in items); ps={p["id"]:p for p in providers()}; logistics=0
    for pid in {x["provider_id"] for x in items}:
        p=ps[pid]; logistics += int(p["shipping"] or 0)+int(p["travel"] or 0) if p["delivery"] in ("Recogida presencial","Ambos") else int(p["shipping"] or 0)
    override=int(st.session_state.get("labor_override",0)); labor=override or (int(s.get("bundle_labor",75000)) if len(items)>1 else int(s.get(f"labor_{items[0]['repair']}",DEFAULT_LABOR.get(items[0]["repair"],40000))) if items else 0)
    base=parts+logistics+labor; rnd=int(s.get("rounding",1000)) or 1; price=lambda m: round((base*(1+m/100))/rnd)*rnd
    return parts,logistics,labor,base,price(s["margin_min"]),price(s["margin_rec"]),price(s["margin_prem"])

st.set_page_config(page_title="BLACK TECH · Cotizador",page_icon="💰",layout="wide")
init_db()
if "quote" not in st.session_state: st.session_state.quote=[]
st.title("BLACK TECH")
st.caption("Base inteligente de precios para reparaciones")
page=st.sidebar.radio("Menú",["Cotizar","Referencias","Proveedores","Configuración","Historial"])

if page=="Cotizar":
    st.header("¿Cuánto cobrar?")
    a,b=st.columns(2); brand=a.text_input("Marca",placeholder="Xiaomi"); model=b.text_input("Modelo / referencia",placeholder="Redmi 13")
    allrefs=list(refs()); repairs=sorted(set(REPAIRS+[r["repair"] for r in allrefs])); repair=st.selectbox("Tipo de reparación",[""]+repairs,format_func=lambda x:"Selecciona..." if not x else x)
    matches=[r for r in allrefs if (not brand or brand.lower() in r["brand"].lower()) and (not model or model.lower() in r["model"].lower()) and (not repair or r["repair"]==repair)]
    if matches:
        labels=[f"{r['quality'] or 'Sin variante'} · {r['provider']} · {money(r['cost'])}" for r in matches]
        idx=st.selectbox("Variante / proveedor",range(len(matches)),format_func=lambda i:labels[i]); selected=matches[idx]
        if st.button("＋ Agregar reparación al cálculo",type="primary"): add_quote(selected); st.rerun()
    elif brand or model or repair: st.warning("No hay referencias guardadas que coincidan con esta combinación.")
    if st.session_state.quote:
        st.subheader("Reparaciones agregadas")
        for i,r in enumerate(st.session_state.quote):
            x,y,z=st.columns([5,2,1]); x.write(f"**{r['repair']} · {r['quality'] or 'Sin variante'}**"); x.caption(f"{r['brand']} {r['model']} · {r['provider']}"); y.write(money(r['cost']))
            if z.button("Quitar",key=f"remove_{i}"): st.session_state.quote.pop(i); st.rerun()
        default_labor=calculate(st.session_state.quote)[2]; st.number_input("Mano de obra",min_value=0,step=1000,value=int(default_labor),key="labor_override")
        parts,logistics,labor,base,pmin,prec,pprem=calculate(st.session_state.quote)
        a,b,c=st.columns(3); a.metric("Repuestos",money(parts)); b.metric("Logística",money(logistics)); c.metric("Mano de obra",money(labor)); st.metric("COSTO REAL",money(base))
        a,b,c=st.columns(3); a.metric("Mínimo",money(pmin)); b.metric("RECOMENDADO",money(prec)); c.metric("Premium",money(pprem))
        if st.button("Guardar cotización"): 
            cdb=db(); payload={"items":st.session_state.quote,"parts":parts,"logistics":logistics,"labor":labor,"base":base,"recommended":prec}; cdb.execute("INSERT INTO history(created_at,data) VALUES(?,?)",(datetime.now().isoformat(timespec="seconds"),json.dumps(payload,ensure_ascii=False))); cdb.commit(); cdb.close(); st.success("Cotización guardada.")
        if st.button("Limpiar cotización"): reset_quote(); st.rerun()
    else: st.info("Selecciona una referencia y agrégala al cálculo. Puedes agregar varias reparaciones.")

elif page=="Referencias":
    st.header("Referencias"); st.caption("Base de repuestos. Aquí no se cotiza.")
    ps=providers()
    with st.form("new_ref"):
        a,b=st.columns(2); brand=a.text_input("Marca"); model=b.text_input("Modelo")
        a,b=st.columns(2); repair=a.selectbox("Tipo de reparación",REPAIRS); quality=b.text_input("Variante / calidad",placeholder="LCD con marco")
        provider=a.selectbox("Proveedor",ps,format_func=lambda p:p["name"]); cost=b.number_input("Costo del repuesto",min_value=0,step=1000); note=st.text_area("Nota")
        if st.form_submit_button("Guardar referencia",type="primary"):
            c=db(); c.execute("INSERT INTO references_(brand,model,repair,quality,provider_id,cost,note) VALUES(?,?,?,?,?,?,?)",(brand.strip(),model.strip(),repair,quality.strip(),provider["id"],cost,note.strip())); c.commit(); c.close(); st.success("Referencia guardada."); st.rerun()
    q=st.text_input("Buscar referencias")
    for r in [x for x in refs() if q.lower() in " ".join(str(x[k] or "") for k in ["brand","model","repair","quality","provider"]).lower()]:
        with st.expander(f"{r['brand']} · {r['model']} · {r['repair']} · {r['quality'] or 'Sin variante'}"): st.write(f"Proveedor: **{r['provider']}** · Repuesto: **{money(r['cost'])}**"); st.caption(r["note"] or "Sin nota")

elif page=="Proveedores":
    st.header("Proveedores")
    for p in providers():
        with st.expander(p["name"]):
            with st.form(f"p{p['id']}"):
                name=st.text_input("Nombre",p["name"]); delivery=st.selectbox("Entrega",["Recogida presencial","Envío","Ambos"],index=["Recogida presencial","Envío","Ambos"].index(p["delivery"])); a,b=st.columns(2); shipping=a.number_input("Envío",min_value=0,step=1000,value=int(p["shipping"])); travel=b.number_input("Desplazamiento",min_value=0,step=1000,value=int(p["travel"])); note=st.text_area("Nota",p["note"] or "")
                if st.form_submit_button("Guardar cambios"):
                    c=db(); c.execute("UPDATE providers SET name=?,delivery=?,shipping=?,travel=?,note=? WHERE id=?",(name.strip(),delivery,shipping,travel,note,p["id"])); c.commit(); c.close(); st.rerun()
    st.divider()
    with st.form("new_provider"):
        name=st.text_input("Nuevo proveedor"); delivery=st.selectbox("Entrega",["Recogida presencial","Envío","Ambos"]); a,b=st.columns(2); shipping=a.number_input("Envío",min_value=0,step=1000); travel=b.number_input("Desplazamiento",min_value=0,step=1000); note=st.text_area("Nota")
        if st.form_submit_button("Agregar proveedor"):
            c=db(); c.execute("INSERT INTO providers(name,delivery,shipping,travel,note) VALUES(?,?,?,?,?)",(name.strip(),delivery,shipping,travel,note)); c.commit(); c.close(); st.rerun()

elif page=="Configuración":
    st.header("Configuración"); s=settings(); st.subheader("Mano de obra por reparación")
    with st.form("labor"):
        vals={k:st.number_input(k,min_value=0,step=1000,value=int(s.get(f"labor_{k}",v))) for k,v in DEFAULT_LABOR.items()}; bundle=st.number_input("Mano de obra combinada",min_value=0,step=1000,value=int(s.get("bundle_labor",75000)))
        if st.form_submit_button("Guardar mano de obra",type="primary"):
            for k,v in vals.items(): save_setting(f"labor_{k}",v)
            save_setting("bundle_labor",bundle); st.rerun()
    st.subheader("Márgenes")
    with st.form("margins"):
        a,b,c=st.columns(3); mi=a.number_input("Mínimo %",min_value=0,value=int(s["margin_min"])); mr=b.number_input("Recomendado %",min_value=0,value=int(s["margin_rec"])); mp=c.number_input("Premium %",min_value=0,value=int(s["margin_prem"])); rnd=st.number_input("Redondear a",min_value=1,step=100,value=int(s["rounding"]))
        if st.form_submit_button("Guardar márgenes"): save_setting("margin_min",mi);save_setting("margin_rec",mr);save_setting("margin_prem",mp);save_setting("rounding",rnd);st.rerun()
    backup={"providers":[dict(x) for x in providers()],"references":[dict(x) for x in refs()],"settings":settings()}; st.download_button("Descargar respaldo JSON",json.dumps(backup,ensure_ascii=False,indent=2),"black-tech-cotizador.json","application/json")

else:
    st.header("Historial"); rows=db().execute("SELECT * FROM history ORDER BY id DESC LIMIT 100").fetchall()
    if not rows: st.info("Todavía no hay cotizaciones guardadas.")
    for h in rows:
        d=json.loads(h["data"]); st.write(f"**{' + '.join(x['model'] for x in d['items'])}** · {' + '.join(x['repair'] for x in d['items'])} · {h['created_at']} · Recomendado: **{money(d['recommended'])}**")
