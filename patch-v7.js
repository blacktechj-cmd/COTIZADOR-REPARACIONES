/* V1.9.2 - Base de mano de obra editable + datos reales Redmi 13 */
(function(){
  const KEY='bt-cotizador-v2';
  const defaults={'Pantalla OLED':65000,'Pantalla LCD':55000,'Batería':40000,'Puerto de carga':60000,'Flex de Encendido/Volumen':35000,'Cámara Trasera':40000,'Cámara Frontal':35000,'Altavoz / Parlante':35000,'Micrófono':35000,'Placa Base (diagnóstico)':30000,'IC de carga / soldadura':80000,'Cambio de vidrio (glass)':70000,'Sensor de huella':45000,'Face ID / sensores':50000,'Limpieza interna':30000,'Flex Carga':45000};
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const uid=p=>p+Date.now().toString(36)+Math.random().toString(36).slice(2,7);

  function ensureData(){
    data.settings=data.settings||{};data.settings.repairLabor=data.settings.repairLabor||{};
    Object.entries(defaults).forEach(([k,v])=>{if(data.settings.repairLabor[k]==null)data.settings.repairLabor[k]=v;});
    const p=data.providers.find(x=>String(x.name||'').trim().toLowerCase()==='markboss repuestos');
    if(p && !p.travelCostConfiguredV19){p.travelCost=12000;p.travelCostConfiguredV19=true;}
    seedRedmi13(p);save();
  }
  function seedRedmi13(p){
    if(!p)return;
    const hasLCD=data.references?.some(r=>String(r.brand).toLowerCase()==='xiaomi'&&String(r.model).toLowerCase()==='redmi 13'&&String(r.repair).toLowerCase()==='pantalla lcd'&&String(r.quality||'').toLowerCase()==='lcd'&&r.providerId===p.id);
    const hasFrame=data.references?.some(r=>String(r.brand).toLowerCase()==='xiaomi'&&String(r.model).toLowerCase()==='redmi 13'&&String(r.repair).toLowerCase()==='pantalla lcd'&&String(r.quality||'').toLowerCase()==='lcd con marco'&&r.providerId===p.id);
    const hasBattery=data.references?.some(r=>String(r.brand).toLowerCase()==='xiaomi'&&String(r.model).toLowerCase()==='redmi 13'&&String(r.repair).toLowerCase()==='batería'&&r.providerId===p.id);
    if(!hasLCD)data.references.push({id:uid('r'),brand:'Xiaomi',model:'Redmi 13',repair:'Pantalla LCD',quality:'LCD',providerId:p.id,cost:35000,note:'Prueba real Redmi 13.'});
    if(!hasFrame)data.references.push({id:uid('r'),brand:'Xiaomi',model:'Redmi 13',repair:'Pantalla LCD',quality:'LCD con marco',providerId:p.id,cost:38000,note:'Alternativa con marco.'});
    if(!hasBattery)data.references.push({id:uid('r'),brand:'Xiaomi',model:'Redmi 13',repair:'Batería',quality:'',providerId:p.id,cost:25000,note:'Prueba real Redmi 13.'});
  }
  function renderLaborConfig(){
    const card=document.getElementById('laborBaseCard');if(!card)return;
    const repairs=[...(data.repairs||[]),...Object.keys(defaults)].filter((v,i,a)=>a.indexOf(v)===i);
    const rows=repairs.map(r=>`<label class="labor-config-row"><span>${esc(r)}</span><input type="number" min="0" step="1000" data-repair-labor="${esc(r)}" value="${Number(data.settings.repairLabor[r]||0)}"></label>`).join('');
    card.innerHTML=`<div class="section-title">Base de mano de obra</div><p class="muted">Estos valores se cargan automáticamente según la reparación. Puedes ajustarlos cuando conozcas mejor el tiempo y dificultad de cada trabajo.</p><div class="labor-config-list">${rows}</div><button id="saveLaborBaseBtn" class="primary full">Guardar mano de obra</button>`;
    document.getElementById('saveLaborBaseBtn').onclick=()=>{card.querySelectorAll('[data-repair-labor]').forEach(i=>data.settings.repairLabor[i.dataset.repairLabor]=Math.max(0,Number(i.value)||0));save();setCurrentLaborFromRepair();alert('Base de mano de obra guardada.');};
  }
  function injectConfig(){if(document.getElementById('laborBaseCard'))return;const view=document.getElementById('view-config');if(!view)return;const card=document.createElement('div');card.id='laborBaseCard';card.className='card';view.querySelector('.card')?.after(card);renderLaborConfig();}
  function laborForRepair(repair){return Number(data.settings?.repairLabor?.[repair])||0;}
  function setCurrentLaborFromRepair(){const repair=document.getElementById('quoteRepair'),input=document.getElementById('laborCost');if(!repair||!input||!repair.value)return;const v=laborForRepair(repair.value);if(v>0){input.value=v;input.dispatchEvent(new Event('input',{bubbles:true}));}}
  function markBossBadge(){const list=document.getElementById('providersList');if(!list)return;list.querySelectorAll('.list-card').forEach(card=>{if(card.querySelector('.travel-v19'))return;if(card.textContent.toLowerCase().includes('markboss')){const d=document.createElement('div');d.className='hint travel-v19';d.textContent='🏍️ Desplazamiento configurado: $12.000';card.appendChild(d);}});}
  function style(){if(document.getElementById('v19-labor-style'))return;const s=document.createElement('style');s.id='v19-labor-style';s.textContent='.labor-config-list{display:grid;gap:8px;margin:12px 0 16px}.labor-config-row{display:grid;grid-template-columns:1fr 130px;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #eef2f7}.labor-config-row span{font-size:14px}.labor-config-row input{width:100%;box-sizing:border-box}.travel-v19{margin-top:10px;background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af}@media(max-width:600px){.labor-config-row{grid-template-columns:1fr 110px}.labor-config-row span{font-size:13px}}';document.head.appendChild(s);}
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>{ensureData();style();injectConfig();markBossBadge();setCurrentLaborFromRepair();document.getElementById('quoteRepair')?.addEventListener('change',setCurrentLaborFromRepair);document.getElementById('quoteReference')?.addEventListener('change',setCurrentLaborFromRepair);const list=document.getElementById('providersList');if(list)new MutationObserver(markBossBadge).observe(list,{childList:true,subtree:true});},450);});
})();
