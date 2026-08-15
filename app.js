const KEY='bt-cotizador-v1';

const defaultData={
  providers:[
    {id:'p1',name:'Proveedor 1',delivery:'Recogida presencial',shipping:0,note:''},
    {id:'p2',name:'Proveedor 2',delivery:'Envío',shipping:0,note:''}
  ],
  repairs:['Pantalla OLED','Pantalla LCD','Batería','Puerto de carga','Flex de Encendido/Volumen','Cámara Trasera','Cámara Frontal','Altavoz / Parlante','Micrófono','Placa Base (diagnóstico)','IC de carga / soldadura','Cambio de vidrio (glass)','Sensor de huella','Face ID / sensores','Limpieza interna','Flex Carga'],
  references:[
    {id:'demo1',brand:'Xiaomi',model:'Redmi 10 2022',repair:'Pantalla LCD',quality:'LCD',providerId:'p1',cost:45000,note:'Ejemplo inicial. Reemplázalo por tu costo real.'}
  ],
  history:[],
  settings:{multMin:2.29,multRec:2.56,multPrem:2.96,rounding:1000}
};

let data=load();
let state={gama:'Media',cliente:'Normal',modo:'Recomendado'};

function load(){try{const raw=localStorage.getItem(KEY);return raw?JSON.parse(raw):structuredClone(defaultData)}catch{return structuredClone(defaultData)}}
function save(){localStorage.setItem(KEY,JSON.stringify(data))}
function money(v){return new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0))}
function roundPrice(v){const r=Number(data.settings.rounding)||1;return Math.round(v/r)*r}
function uid(prefix='id'){return prefix+Date.now().toString(36)+Math.random().toString(36).slice(2,7)}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}

function init(){
  document.querySelectorAll('.bottom-nav button').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
  document.querySelectorAll('.segmented').forEach(group=>group.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{group.querySelectorAll('button').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');state[group.dataset.group]=b.dataset.value;calculate()})));
  ['quoteBrand','quoteModel'].forEach(id=>document.getElementById(id).addEventListener('input',updateQuoteReferences));
  document.getElementById('quoteRepair').addEventListener('change',updateQuoteReferences);
  document.getElementById('quoteReference').addEventListener('change',calculate);
  document.getElementById('saveQuoteBtn').addEventListener('click',saveQuote);
  document.getElementById('newRefBtn').addEventListener('click',openReferenceDialog);
  document.getElementById('newProviderBtn').addEventListener('click',()=>document.getElementById('providerDialog').showModal());
  document.getElementById('referenceForm').addEventListener('submit',saveReferenceFromForm);
  document.getElementById('providerForm').addEventListener('submit',saveProviderFromForm);
  document.getElementById('searchRef').addEventListener('input',renderReferences);
  document.getElementById('saveConfigBtn').addEventListener('click',saveConfig);
  document.getElementById('exportBtn').addEventListener('click',exportData);
  document.getElementById('importInput').addEventListener('change',importData);
  document.getElementById('clearBtn').addEventListener('click',clearData);
  fillRepairs();fillConfig();renderProviders();renderReferences();renderHistory();updateDatalists();updateQuoteReferences();
}

function showView(name){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${name}`));document.querySelectorAll('.bottom-nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===name));if(name==='catalogo')renderReferences();if(name==='proveedores')renderProviders();if(name==='historial')renderHistory()}
function fillRepairs(){const s=document.getElementById('quoteRepair');s.innerHTML='<option value="">Selecciona...</option>'+data.repairs.map(r=>`<option>${esc(r)}</option>`).join('')}
function updateDatalists(){document.getElementById('brandsList').innerHTML=[...new Set(data.references.map(r=>r.brand))].sort().map(x=>`<option value="${esc(x)}">`).join('');document.getElementById('modelsList').innerHTML=[...new Set(data.references.map(r=>r.model))].sort().map(x=>`<option value="${esc(x)}">`).join('')}
function updateQuoteReferences(){
  const brand=document.getElementById('quoteBrand').value.trim().toLowerCase(),model=document.getElementById('quoteModel').value.trim().toLowerCase(),repair=document.getElementById('quoteRepair').value;
  const matches=data.references.filter(r=>(!brand||r.brand.toLowerCase().includes(brand))&&(!model||r.model.toLowerCase().includes(model))&&(!repair||r.repair===repair));
  const s=document.getElementById('quoteReference');
  s.innerHTML='<option value="">Selecciona una referencia...</option>'+matches.map(r=>{const p=data.providers.find(x=>x.id===r.providerId);return `<option value="${r.id}">${esc(r.brand)} ${esc(r.model)} · ${esc(r.repair)} · ${esc(p?.name||'Sin proveedor')} · ${money(r.cost)}</option>`}).join('');
  document.getElementById('referenceInfo').textContent=matches.length?`${matches.length} referencia(s) encontrada(s). Selecciona una para calcular.`:'No hay referencias guardadas para esta búsqueda. Puedes crear una desde “Referencias”.';
  calculate();
}
function calculate(){
  const ref=data.references.find(r=>r.id===document.getElementById('quoteReference').value);const cost=ref?.cost||0;
  const min=roundPrice(cost*Number(data.settings.multMin||0));const rec=roundPrice(cost*Number(data.settings.multRec||0));const prem=roundPrice(cost*Number(data.settings.multPrem||0));
  document.getElementById('selectedCost').textContent=money(cost);document.getElementById('priceMin').textContent=money(min);document.getElementById('priceRecommended').textContent=money(rec);document.getElementById('pricePremium').textContent=money(prem);
}
function saveQuote(){
  const ref=data.references.find(r=>r.id===document.getElementById('quoteReference').value);if(!ref){alert('Selecciona una referencia primero.');return}
  data.history.unshift({id:uid('h'),date:new Date().toISOString(),referenceId:ref.id,gama:state.gama,cliente:state.cliente,modo:state.modo,min:roundPrice(ref.cost*data.settings.multMin),recommended:roundPrice(ref.cost*data.settings.multRec),premium:roundPrice(ref.cost*data.settings.multPrem)});data.history=data.history.slice(0,100);save();renderHistory();alert('Cálculo guardado.');
}
function renderReferences(){const q=document.getElementById('searchRef').value.toLowerCase();const list=document.getElementById('referencesList');const rows=data.references.filter(r=>[r.brand,r.model,r.repair,r.quality,data.providers.find(p=>p.id===r.providerId)?.name].join(' ').toLowerCase().includes(q));if(!rows.length){list.innerHTML='<div class="empty">No hay referencias que coincidan.</div>';return}list.innerHTML=rows.map(r=>{const p=data.providers.find(x=>x.id===r.providerId);return `<article class="list-card"><h3>${esc(r.brand)} · ${esc(r.model)}</h3><div class="meta">${esc(r.repair)} ${r.quality?`· ${esc(r.quality)}`:''}</div><div class="price-row"><div><div class="price">${money(r.cost)}</div><div class="meta">${esc(p?.name||'Sin proveedor')} · ${esc(p?.delivery||'')}</div></div><button class="secondary" onclick="useReference('${r.id}')">Cotizar</button></div>${r.note?`<div class="hint">${esc(r.note)}</div>`:''}</article>`}).join('')}
function useReference(id){const r=data.references.find(x=>x.id===id);if(!r)return;document.getElementById('quoteBrand').value=r.brand;document.getElementById('quoteModel').value=r.model;document.getElementById('quoteRepair').value=r.repair;updateQuoteReferences();document.getElementById('quoteReference').value=r.id;calculate();showView('cotizador')}
function openReferenceDialog(){const select=document.getElementById('dialogProvider');select.innerHTML=data.providers.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');document.getElementById('referenceForm').reset();document.getElementById('referenceDialog').showModal()}
function saveReferenceFromForm(e){e.preventDefault();const f=new FormData(e.target);const brand=f.get('brand').trim(),model=f.get('model').trim(),repair=f.get('repair').trim(),providerId=f.get('provider');const duplicate=data.references.find(r=>r.brand.toLowerCase()===brand.toLowerCase()&&r.model.toLowerCase()===model.toLowerCase()&&r.repair.toLowerCase()===repair.toLowerCase()&&r.providerId===providerId);if(duplicate){duplicate.cost=Number(f.get('cost'));duplicate.quality=f.get('quality').trim();duplicate.note=f.get('note').trim();alert('La referencia ya existía. Se actualizó su costo.')}else data.references.push({id:uid('r'),brand,model,repair,quality:f.get('quality').trim(),providerId,cost:Number(f.get('cost')),note:f.get('note').trim()});save();e.target.closest('dialog').close();fillRepairs();updateDatalists();renderReferences();updateQuoteReferences()}
function renderProviders(){const list=document.getElementById('providersList');list.innerHTML=data.providers.map(p=>`<article class="list-card"><h3>${esc(p.name)}</h3><div class="meta">${esc(p.delivery)} · Envío: ${money(p.shipping)}</div>${p.note?`<div class="hint">${esc(p.note)}</div>`:''}</article>`).join('')||'<div class="empty">No hay proveedores.</div>'}
function saveProviderFromForm(e){e.preventDefault();const f=new FormData(e.target);data.providers.push({id:uid('p'),name:f.get('name').trim(),delivery:f.get('delivery'),shipping:Number(f.get('shipping'))||0,note:f.get('note').trim()});save();e.target.closest('dialog').close();renderProviders()}
function fillConfig(){document.getElementById('multMin').value=data.settings.multMin;document.getElementById('multRec').value=data.settings.multRec;document.getElementById('multPrem').value=data.settings.multPrem;document.getElementById('rounding').value=data.settings.rounding}
function saveConfig(){data.settings={multMin:Number(document.getElementById('multMin').value)||1,multRec:Number(document.getElementById('multRec').value)||1,multPrem:Number(document.getElementById('multPrem').value)||1,rounding:Number(document.getElementById('rounding').value)||1};save();calculate();alert('Configuración guardada.')}
function renderHistory(){const list=document.getElementById('historyList');if(!data.history.length){list.innerHTML='<div class="empty">Todavía no hay cálculos guardados.</div>';return}list.innerHTML=data.history.map(h=>{const r=data.references.find(x=>x.id===h.referenceId);return `<article class="list-card"><h3>${r?`${esc(r.brand)} · ${esc(r.model)}`:'Referencia eliminada'}</h3><div class="meta">${r?esc(r.repair):''} · ${new Date(h.date).toLocaleString('es-CO')}</div><div class="tags"><span class="tag">${esc(h.gama)}</span><span class="tag">${esc(h.cliente)}</span><span class="tag">${esc(h.modo)}</span></div><div class="price-row"><span>Mínimo ${money(h.min)}</span><strong>Recomendado ${money(h.recommended)}</strong><span>Premium ${money(h.premium)}</span></div></article>`}).join('')}
function exportData(){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`black-tech-cotizador-${new Date().toISOString().slice(0,10)}.json`;a.click();URL.revokeObjectURL(a.href)}
function importData(e){const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{try{const incoming=JSON.parse(reader.result);if(!incoming.references||!incoming.providers||!incoming.settings)throw Error();data=incoming;save();fillRepairs();fillConfig();updateDatalists();renderProviders();renderReferences();renderHistory();updateQuoteReferences();alert('Respaldo importado.')}catch{alert('El archivo no tiene un formato válido.')}};reader.readAsText(file);e.target.value=''}
function clearData(){if(!confirm('¿Borrar todas las referencias, proveedores e historial de este dispositivo?'))return;localStorage.removeItem(KEY);data=structuredClone(defaultData);fillRepairs();fillConfig();updateDatalists();renderProviders();renderReferences();renderHistory();updateQuoteReferences()}

window.useReference=useReference;document.addEventListener('DOMContentLoaded',init);
