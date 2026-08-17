/* V1.9 - Cotización real: múltiples reparaciones, logística y edición de proveedores */
(function(){
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  const uid=p=>p+Date.now().toString(36)+Math.random().toString(36).slice(2,7);
  const KEY='bt-cotizador-v2';
  const repairLabor={'Pantalla LCD':55000,'Pantalla OLED':65000,'Batería':40000,'Puerto de carga':60000,'Flex de Encendido/Volumen':35000,'Cámara Trasera':40000,'Cámara Frontal':35000,'Altavoz / Parlante':35000,'Micrófono':35000,'Placa Base (diagnóstico)':30000,'IC de carga / soldadura':80000,'Cambio de vidrio (glass)':70000,'Sensor de huella':45000,'Face ID / sensores':50000,'Limpieza interna':30000,'Flex Carga':45000};
  let quoteItems=[];
  function getData(){try{return JSON.parse(localStorage.getItem(KEY))||null}catch{return null}}
  function saveData(d){localStorage.setItem(KEY,JSON.stringify(d))}
  function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
  function refById(id){return getData()?.references?.find(r=>r.id===id)}
  function providerById(id){return getData()?.providers?.find(p=>p.id===id)}
  function laborFor(repair){const d=getData();return Number(d?.settings?.laborByRepair?.[repair] ?? repairLabor[repair] ?? 0)}
  function round(v){const d=getData(),r=Number(d?.settings?.rounding)||1;return Math.round(v/r)*r}

  function seedRealTestData(){
    const d=getData();if(!d)return;
    d.settings=d.settings||{};d.settings.laborByRepair=d.settings.laborByRepair||{};
    Object.entries(repairLabor).forEach(([k,v])=>{if(d.settings.laborByRepair[k]==null)d.settings.laborByRepair[k]=v});
    if(d.settings.bundleLabor==null)d.settings.bundleLabor=75000;
    let p=d.providers.find(x=>String(x.name||'').trim().toLowerCase()==='markboss repuestos');
    if(!p){p={id:uid('p'),name:'MarkBoss Repuestos',delivery:'Recogida presencial',shipping:0,travel:12000,note:'Desplazamiento estimado: $12.000.'};d.providers.push(p)}else{p.travel=12000;p.shipping=0;p.delivery='Recogida presencial'}
    const ensure=(repair,quality,cost,note)=>{if(!d.references.some(r=>String(r.brand).toLowerCase()==='xiaomi'&&String(r.model).toLowerCase()==='redmi 13'&&String(r.repair).toLowerCase()===repair.toLowerCase()&&r.providerId===p.id))d.references.push({id:uid('r'),brand:'Xiaomi',model:'Redmi 13',repair,quality,providerId:p.id,cost,note})};
    ensure('Pantalla LCD','LCD',35000,'Prueba real: LCD sin marco.');
    ensure('Batería','Batería',25000,'Prueba real.');
    saveData(d);
  }

  function resetQuote(){
    quoteItems=[];
    ['quoteBrand','quoteModel','quoteRepair','quoteReference','laborCost'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=''});
    ['providerComparison','quoteItems','quoteBreakdown'].forEach(id=>{const e=document.getElementById(id);if(e)e.innerHTML=''});
    const info=document.getElementById('referenceInfo');if(info)info.textContent='Escribe marca y modelo para buscar referencias guardadas.';
    ['baseCost','selectedCost'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=money(0)});
    ['priceMin','priceRecommended','pricePremium'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=money(0)});
  }

  function addCurrentReference(){
    const id=document.getElementById('quoteReference')?.value;if(!id)return alert('Selecciona una referencia primero.');
    if(quoteItems.some(x=>x.referenceId===id))return alert('Esta referencia ya está agregada.');
    const r=refById(id);if(!r)return;quoteItems.push({referenceId:id,labor:laborFor(r.repair)});renderQuoteItems();renderQuoteSummary();
  }
  function renderQuoteItems(){
    const box=document.getElementById('quoteItems');if(!box)return;
    if(!quoteItems.length){box.innerHTML='<div class="hint">Selecciona una referencia y pulsa «Agregar reparación».</div>';return}
    box.innerHTML='<div class="field-label">Reparaciones de esta cotización</div>'+quoteItems.map((it,i)=>{const r=refById(it.referenceId),p=providerById(r?.providerId);return `<article class="quote-item"><div><strong>${r?esc(r.brand)+' · '+esc(r.model):'Referencia'}</strong><div class="meta">${esc(r?.repair||'')} ${r?.quality?'· '+esc(r.quality):''}</div><div class="meta">${esc(p?.name||'Sin proveedor')} · Repuesto ${money(r?.cost||0)}</div></div><div class="quote-item-controls"><label>Mano de obra<input type="number" min="0" step="1000" value="${Math.round(it.labor)}" data-labor-index="${i}"></label><button type="button" class="danger-outline" data-remove-index="${i}">Quitar</button></div></article>`}).join('');
    box.querySelectorAll('[data-remove-index]').forEach(b=>b.onclick=()=>{quoteItems.splice(Number(b.dataset.removeIndex),1);renderQuoteItems();renderQuoteSummary()});
    box.querySelectorAll('[data-labor-index]').forEach(e=>e.oninput=()=>{quoteItems[Number(e.dataset.laborIndex)].labor=Math.max(0,Number(e.value)||0);renderQuoteSummary()});
  }
  function renderQuoteSummary(){
    const d=getData();if(!d)return;let parts=0,travel=0,shipping=0,labor=0;
    quoteItems.forEach(it=>{const r=refById(it.referenceId),p=providerById(r?.providerId);parts+=Number(r?.cost)||0;travel+=Number(p?.travel)||0;shipping+=Number(p?.shipping)||0;labor+=Number(it.labor)||0});
    if(quoteItems.length>1)labor=Number(d.settings.bundleLabor)||75000;
    const base=parts+travel+shipping+labor,min=round(base*(1+(Number(d.settings.marginMin)||0)/100)),rec=round(base*(1+(Number(d.settings.marginRec)||0)/100)),prem=round(base*(1+(Number(d.settings.marginPrem)||0)/100));
    const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=money(v)};set('selectedCost',base);set('priceMin',min);set('priceRecommended',rec);set('pricePremium',prem);const b=document.getElementById('baseCost');if(b)b.value=money(base);
    const bd=document.getElementById('quoteBreakdown');if(bd)bd.innerHTML=`<div><span>Repuestos</span><strong>${money(parts)}</strong></div><div><span>Desplazamiento</span><strong>${money(travel)}</strong></div><div><span>Domicilio</span><strong>${money(shipping)}</strong></div><div><span>Mano de obra ${quoteItems.length>1?'combinada':''}</span><strong>${money(labor)}</strong></div><hr><div class="total-line"><span>Costo real</span><strong>${money(base)}</strong></div>`;
  }
  function buildMultiUI(){
    const card=document.querySelector('#view-cotizador .card');if(!card||document.getElementById('quoteItems'))return;
    const grid=card.querySelector('.grid.two:last-of-type');if(grid)grid.style.display='none';
    const wrap=document.createElement('div');wrap.innerHTML='<div id="quoteItems"></div><div class="quote-add-row"><button type="button" id="addRepairBtn" class="secondary">＋ Agregar reparación</button></div><div id="quoteBreakdown" class="quote-breakdown"></div>';
    document.getElementById('referenceInfo')?.insertAdjacentElement('afterend',wrap);document.getElementById('addRepairBtn').onclick=addCurrentReference;
  }

  function rebuildProviderSelect(){const s=document.getElementById('dialogProvider');if(!s)return;const d=getData();s.innerHTML='<option value="">Selecciona un proveedor...</option>'+d.providers.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}
  function openEditReference(id){const d=getData(),r=d.references.find(x=>x.id===id),form=document.getElementById('referenceForm');if(!r||!form)return;form.dataset.editId=id;rebuildProviderSelect();form.elements.brand.value=r.brand;form.elements.model.value=r.model;form.elements.repair.value=r.repair;form.elements.quality.value=r.quality||'';form.elements.provider.value=d.providers.some(p=>p.id===r.providerId)?r.providerId:'';form.elements.cost.value=r.cost;form.elements.note.value=r.note||'';form.querySelector('h2').textContent='Editar referencia';form.querySelector('button[value="default"]').textContent='Guardar cambios';document.getElementById('referenceDialog').showModal()}
  function installReferenceButtons(){const list=document.getElementById('referencesList');if(!list)return;list.querySelectorAll('.list-card').forEach(card=>{if(card.querySelector('.edit-reference'))return;const q=card.querySelector('button[onclick*="useReference"]');if(!q)return;const m=(q.getAttribute('onclick')||'').match(/useReference\(['\"]([^'\"]+)/);if(!m)return;const b=document.createElement('button');b.type='button';b.className='secondary edit-reference';b.textContent='Editar';b.onclick=()=>openEditReference(m[1]);(q.parentElement||card).appendChild(b)})}
  function addTravelToProviderForm(){const form=document.getElementById('providerForm');if(!form||form.querySelector('[name="travel"]'))return;const note=form.elements.note;const lab=document.createElement('label');lab.innerHTML='Costo de desplazamiento<input name="travel" type="number" min="0" step="1000" value="0"><small class="muted">Costo estimado de ir a recoger el repuesto.</small>';note.parentElement.insertBefore(lab,note.parentElement.querySelector('button'))}
  function renderProviders(){const d=getData(),list=document.getElementById('providersList');if(!list)return;list.innerHTML=d.providers.map(p=>`<article class="list-card"><h3>${esc(p.name)}</h3><div class="meta">${esc(p.delivery)} · Envío: ${money(p.shipping||0)} · Desplazamiento: ${money(p.travel||0)}</div>${p.note?`<div class="hint">${esc(p.note)}</div>`:''}<div class="reference-actions"><button type="button" class="secondary" data-provider-edit="${p.id}">Editar</button></div></article>`).join('');list.querySelectorAll('[data-provider-edit]').forEach(b=>b.onclick=()=>openProviderEdit(b.dataset.providerEdit))}
  function openProviderEdit(id){const p=providerById(id);if(!p)return;let dlg=document.getElementById('providerEditDialog');if(!dlg){dlg=document.createElement('dialog');dlg.id='providerEditDialog';dlg.innerHTML='<form method="dialog" class="modal" id="providerEditForm"><div class="modal-head"><h2>Editar proveedor</h2><button value="cancel" class="icon-btn">✕</button></div><label>Nombre<input name="name" required></label><label>Entrega<select name="delivery"><option>Recogida presencial</option><option>Envío</option><option>Ambos</option></select></label><label>Costo de envío<input name="shipping" type="number" min="0" step="100"></label><label>Costo de desplazamiento<input name="travel" type="number" min="0" step="1000"></label><label>Nota<textarea name="note" rows="2"></textarea></label><button class="primary full" value="default">Guardar cambios</button></form>';document.body.appendChild(dlg);dlg.querySelector('form').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target),d=getData(),x=d.providers.find(q=>q.id===dlg.dataset.id);x.name=String(f.get('name')).trim();x.delivery=f.get('delivery');x.shipping=Number(f.get('shipping'))||0;x.travel=Number(f.get('travel'))||0;x.note=String(f.get('note')).trim();saveData(d);dlg.close();renderProviders()}}
    dlg.dataset.id=id;const f=dlg.querySelector('form');f.elements.name.value=p.name;f.elements.delivery.value=p.delivery;f.elements.shipping.value=p.shipping||0;f.elements.travel.value=p.travel||0;f.elements.note.value=p.note||'';dlg.showModal()}
  function addLaborConfig(){const card=[...document.querySelectorAll('#view-config .card')].find(c=>c.textContent.includes('Mano de obra'));if(!card||document.getElementById('repairLaborConfig'))return;const d=getData(),wrap=document.createElement('div');wrap.id='repairLaborConfig';wrap.innerHTML='<div class="section-title">Mano de obra por reparación</div><div class="grid two">'+Object.keys(repairLabor).map(k=>`<label>${esc(k)}<input type="number" min="0" step="1000" data-labor-repair="${esc(k)}" value="${Number(d.settings.laborByRepair?.[k]??repairLabor[k])}"></label>`).join('')+'</div><label>Mano de obra combinada (2 o más reparaciones)<input id="bundleLabor" type="number" min="0" step="1000" value="'+Number(d.settings.bundleLabor||75000)+'"></label><button type="button" id="saveRepairLabor" class="secondary full">Guardar mano de obra</button>';card.appendChild(wrap);wrap.querySelector('#saveRepairLabor').onclick=()=>{const x=getData();x.settings.laborByRepair=x.settings.laborByRepair||{};wrap.querySelectorAll('[data-labor-repair]').forEach(e=>x.settings.laborByRepair[e.dataset.laborRepair]=Number(e.value)||0);x.settings.bundleLabor=Number(wrap.querySelector('#bundleLabor').value)||0;saveData(x);renderQuoteSummary();alert('Mano de obra actualizada.')}}
  function patch(){seedRealTestData();buildMultiUI();addTravelToProviderForm();addLaborConfig();renderProviders();installReferenceButtons();
    const clear=document.getElementById('clearQuoteBtn');if(clear)clear.onclick=resetQuote;
    document.getElementById('newRefBtn')?.addEventListener('click',rebuildProviderSelect);
    const refForm=document.getElementById('referenceForm');refForm?.addEventListener('submit',e=>{const id=refForm.dataset.editId;if(!id)return;e.preventDefault();e.stopImmediatePropagation();const f=new FormData(refForm),d=getData(),r=d.references.find(x=>x.id===id),pid=String(f.get('provider')||'');if(!pid||!d.providers.some(p=>p.id===pid))return alert('Selecciona un proveedor válido.');r.brand=String(f.get('brand')).trim();r.model=String(f.get('model')).trim();r.repair=String(f.get('repair')).trim();r.quality=String(f.get('quality')||'').trim();r.providerId=pid;r.cost=Math.max(0,Number(f.get('cost'))||0);r.note=String(f.get('note')||'').trim();saveData(d);refForm.close?.();document.getElementById('referenceDialog').close();delete refForm.dataset.editId;alert('Referencia actualizada.');window.location.reload()},true);
    const list=document.getElementById('referencesList');if(list)new MutationObserver(()=>installReferenceButtons()).observe(list,{childList:true,subtree:true});
    resetQuote();renderQuoteItems();renderQuoteSummary();
  }
  document.addEventListener('DOMContentLoaded',()=>setTimeout(patch,700));
})();
