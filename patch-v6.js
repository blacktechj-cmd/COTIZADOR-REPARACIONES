/* V2.0 - Cotización corregida: seleccionar NO agrega; solo "Agregar reparación" agrega */
(function(){
  const KEY='bt-cotizador-v2';
  const repairLabor={'Pantalla LCD':55000,'Pantalla OLED':65000,'Batería':40000,'Puerto de carga':60000,'Flex de Encendido/Volumen':35000,'Cámara Trasera':40000,'Cámara Frontal':35000,'Altavoz / Parlante':35000,'Micrófono':35000,'Placa Base (diagnóstico)':30000,'IC de carga / soldadura':80000,'Cambio de vidrio (glass)':70000,'Sensor de huella':45000,'Face ID / sensores':50000,'Limpieza interna':30000,'Flex Carga':45000};
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  const uid=p=>p+Date.now().toString(36)+Math.random().toString(36).slice(2,7);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  let quoteItems=[];
  function getData(){try{return JSON.parse(localStorage.getItem(KEY))||null}catch{return null}}
  function saveData(d){localStorage.setItem(KEY,JSON.stringify(d))}
  function refById(id){return getData()?.references?.find(r=>r.id===id)}
  function providerById(id){return getData()?.providers?.find(p=>p.id===id)}
  function laborFor(repair){const d=getData();return Number(d?.settings?.laborByRepair?.[repair] ?? d?.settings?.repairLabor?.[repair] ?? repairLabor[repair] ?? 0)}
  function round(v){const d=getData(),r=Number(d?.settings?.rounding)||1;return Math.round(v/r)*r}
  function providerCost(r){const p=providerById(r?.providerId);const shipping=Number(p?.shipping)||0;const travel=Number(p?.travelCost ?? p?.travel)||0;const delivery=String(p?.delivery||'').toLowerCase();const trip=delivery.includes('recogida')?travel:0;return {p,shipping,travel:trip,total:(Number(r?.cost)||0)+shipping+trip}}
  function selectedId(){return document.getElementById('quoteReference')?.value||state.selectedReferenceId||''}
  function selectedRef(){return refById(selectedId())}

  function seedRealData(){
    const d=getData();if(!d)return;
    d.settings=d.settings||{};d.settings.laborByRepair=d.settings.laborByRepair||{};d.settings.repairLabor=d.settings.repairLabor||{};
    Object.entries(repairLabor).forEach(([k,v])=>{if(d.settings.laborByRepair[k]==null)d.settings.laborByRepair[k]=Number(d.settings.repairLabor[k]??v);if(d.settings.repairLabor[k]==null)d.settings.repairLabor[k]=d.settings.laborByRepair[k]});
    if(d.settings.bundleLabor==null)d.settings.bundleLabor=75000;
    let p=d.providers.find(x=>String(x.name||'').trim().toLowerCase()==='markboss repuestos');
    if(!p){p={id:uid('p'),name:'MarkBoss Repuestos',delivery:'Recogida presencial',shipping:0,travelCost:12000,note:'Desplazamiento estimado: $12.000.'};d.providers.push(p)}else{p.travelCost=12000;p.shipping=0;p.delivery='Recogida presencial';p.note=p.note||'Desplazamiento estimado: $12.000.'}
    const ensure=(repair,quality,cost,note)=>{if(!d.references.some(r=>String(r.brand).toLowerCase()==='xiaomi'&&String(r.model).toLowerCase()==='redmi 13'&&String(r.repair).toLowerCase()===repair.toLowerCase()&&r.providerId===p.id))d.references.push({id:uid('r'),brand:'Xiaomi',model:'Redmi 13',repair,quality,providerId:p.id,cost,note})};
    ensure('Pantalla LCD','LCD',35000,'Prueba real: LCD sin marco.');
    ensure('Batería','Batería',25000,'Prueba real.');
    saveData(d);
  }

  function laborSingle(r){const input=document.getElementById('laborCost');const manual=Number(input?.value)||0;return manual||laborFor(r?.repair)}
  function combinedLabor(){const d=getData();if(quoteItems.length<=1)return Number(quoteItems[0]?.labor)||0;return Number(d?.settings?.bundleLabor)||75000}

  function renderQuoteItems(){
    const box=document.getElementById('quoteItems');if(!box)return;
    if(!quoteItems.length){box.innerHTML='<div class="hint">Selecciona una referencia y pulsa «Agregar reparación» para incluirla en la cotización.</div>';return}
    box.innerHTML='<div class="field-label">Reparaciones incluidas en esta cotización</div>'+quoteItems.map((it,i)=>{const r=refById(it.referenceId),c=providerCost(r);return `<article class="quote-item"><div><strong>${r?esc(r.brand)+' · '+esc(r.model):'Referencia'}</strong><div class="meta">${esc(r?.repair||'')} ${r?.quality?'· '+esc(r.quality):''}</div><div class="meta">${esc(c.p?.name||'Sin proveedor')} · Repuesto ${money(r?.cost||0)}${c.travel?` · Desplazamiento ${money(c.travel)}`:''}</div></div><div class="quote-item-controls"><label>Mano de obra<input type="number" min="0" step="1000" value="${Math.round(it.labor)}" data-labor-index="${i}"></label><button type="button" class="danger-outline" data-remove-index="${i}">Quitar</button></div></article>`}).join('');
    box.querySelectorAll('[data-remove-index]').forEach(b=>b.onclick=()=>{quoteItems.splice(Number(b.dataset.removeIndex),1);renderQuoteItems();renderQuoteSummary()});
    box.querySelectorAll('[data-labor-index]').forEach(e=>e.oninput=()=>{quoteItems[Number(e.dataset.laborIndex)].labor=Math.max(0,Number(e.value)||0);renderQuoteSummary()});
  }

  function renderQuoteSummary(){
    const d=getData();if(!d)return;
    let parts=0,travel=0,shipping=0,labor=0;
    if(quoteItems.length){
      quoteItems.forEach(it=>{const r=refById(it.referenceId),c=providerCost(r);parts+=Number(r?.cost)||0;travel+=c.travel;shipping+=c.shipping});
      labor=combinedLabor();
    }else{
      const r=selectedRef();
      if(r){const c=providerCost(r);parts=Number(r.cost)||0;travel=c.travel;shipping=c.shipping;labor=laborSingle(r)}
    }
    const base=parts+travel+shipping+labor;
    const min=round(base*(1+(Number(d.settings.marginMin)||0)/100)),rec=round(base*(1+(Number(d.settings.marginRec)||0)/100)),prem=round(base*(1+(Number(d.settings.marginPrem)||0)/100));
    const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=money(v)};
    set('selectedCost',base);set('priceMin',min);set('priceRecommended',rec);set('pricePremium',prem);
    const b=document.getElementById('baseCost');if(b)b.value=money(base);
    const bd=document.getElementById('quoteBreakdown');if(bd)bd.innerHTML=base?`<div><span>Repuestos</span><strong>${money(parts)}</strong></div>${travel?`<div><span>Desplazamiento</span><strong>${money(travel)}</strong></div>`:''}${shipping?`<div><span>Envío</span><strong>${money(shipping)}</strong></div>`:''}<div><span>Mano de obra${quoteItems.length>1?' combinada':''}</span><strong>${money(labor)}</strong></div><hr><div class="total-line"><span>Costo real</span><strong>${money(base)}</strong></div>`:'';
  }

  function renderProviderComparisonFixed(matches){
    const box=document.getElementById('providerComparison');if(!box)return;if(!matches.length){box.innerHTML='';return}
    box.innerHTML='<div class="field-label">Comparación de proveedores</div>'+matches.map(r=>{const c=providerCost(r),sel=r.id===state.selectedReferenceId;return `<button type="button" class="provider-option ${sel?'selected':''}" data-fixed-ref="${r.id}"><span><strong>${esc(c.p?.name||'Sin proveedor')}</strong><small>${esc(c.p?.delivery||'')} · Repuesto ${money(r.cost)}${c.travel?` · Desplazamiento ${money(c.travel)}`:''}${c.shipping?` · Envío ${money(c.shipping)}`:''}</small></span><strong>${money(c.total)}</strong></button>`}).join('');
    box.querySelectorAll('[data-fixed-ref]').forEach(b=>b.onclick=()=>{state.selectedReferenceId=b.dataset.fixedRef;const s=document.getElementById('quoteReference');if(s)s.value=b.dataset.fixedRef;renderProviderComparisonFixed(currentMatchesFixed());setCurrentLabor();renderQuoteSummary()});
  }
  function currentMatchesFixed(){const b=document.getElementById('quoteBrand')?.value.trim().toLowerCase()||'',m=document.getElementById('quoteModel')?.value.trim().toLowerCase()||'',r=document.getElementById('quoteRepair')?.value||'';return (getData()?.references||[]).filter(x=>(!b||String(x.brand).toLowerCase().includes(b))&&(!m||String(x.model).toLowerCase().includes(m))&&(!r||x.repair===r))}
  function setCurrentLabor(){const r=selectedRef(),input=document.getElementById('laborCost');if(!r||!input)return;input.value=laborFor(r.repair)}

  function addCurrentReference(){
    const id=selectedId();if(!id)return alert('Selecciona una referencia primero.');
    if(quoteItems.some(x=>x.referenceId===id))return alert('Esta referencia ya está agregada.');
    const r=refById(id);if(!r)return;
    quoteItems.push({referenceId:id,labor:laborFor(r.repair)});renderQuoteItems();renderQuoteSummary();
  }
  function resetQuote(){quoteItems=[];state.selectedReferenceId='';['quoteBrand','quoteModel','quoteRepair','quoteReference','laborCost'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=''});['providerComparison','quoteItems','quoteBreakdown'].forEach(id=>{const e=document.getElementById(id);if(e)e.innerHTML=''});const info=document.getElementById('referenceInfo');if(info)info.textContent='Escribe marca y modelo para buscar referencias guardadas.';renderQuoteItems();renderQuoteSummary()}

  function buildMultiUI(){
    const card=document.querySelector('#view-cotizador .card');if(!card)return;
    const old=document.getElementById('quoteItems');if(old)old.remove();
    const oldAdd=document.getElementById('addRepairBtn');if(oldAdd)oldAdd.remove();
    const refInfo=document.getElementById('referenceInfo');if(!refInfo)return;
    const wrap=document.createElement('div');wrap.innerHTML='<div id="quoteItems"></div><div class="quote-add-row"><button type="button" id="addRepairBtn" class="secondary full">＋ Agregar reparación a esta cotización</button></div><div id="quoteBreakdown" class="quote-breakdown"></div>';refInfo.insertAdjacentElement('afterend',wrap);document.getElementById('addRepairBtn').onclick=addCurrentReference;
  }

  function rebuildProviderSelect(){const s=document.getElementById('dialogProvider');const d=getData();if(!s||!d)return;s.innerHTML='<option value="">Selecciona un proveedor...</option>'+d.providers.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}
  function installReferenceEditors(){const list=document.getElementById('referencesList');if(!list)return;list.querySelectorAll('.list-card').forEach(card=>{if(card.querySelector('.edit-reference'))return;const q=card.querySelector('button[onclick*="useReference"]');if(!q)return;const m=(q.getAttribute('onclick')||'').match(/useReference\(['\"]([^'\"]+)/);if(!m)return;const b=document.createElement('button');b.type='button';b.className='secondary edit-reference';b.textContent='Editar';b.onclick=()=>openEditReference(m[1]);(q.parentElement||card).appendChild(b)})}
  function openEditReference(id){const d=getData(),r=d.references.find(x=>x.id===id),form=document.getElementById('referenceForm');if(!r||!form)return;rebuildProviderSelect();form.dataset.editId=id;form.elements.brand.value=r.brand;form.elements.model.value=r.model;form.elements.repair.value=r.repair;form.elements.quality.value=r.quality||'';form.elements.provider.value=r.providerId;form.elements.cost.value=r.cost;form.elements.note.value=r.note||'';form.querySelector('h2').textContent='Editar referencia';form.querySelector('button[value="default"]').textContent='Guardar cambios';document.getElementById('referenceDialog').showModal()}
  function addProviderTravelField(){const form=document.getElementById('providerForm');if(!form||form.elements.travel)return;const lab=document.createElement('label');lab.innerHTML='Costo de desplazamiento<input name="travel" type="number" min="0" step="1000" value="0"><small class="muted">Costo estimado de ir a recoger el repuesto.</small>';form.elements.note.parentElement.insertBefore(lab,form.querySelector('button'))}
  function renderProvidersFixed(){const d=getData(),list=document.getElementById('providersList');if(!list||!d)return;list.innerHTML=d.providers.map(p=>`<article class="list-card"><h3>${esc(p.name)}</h3><div class="meta">${esc(p.delivery)} · Envío: ${money(p.shipping||0)} · Desplazamiento: ${money(p.travelCost??p.travel??0)}</div>${p.note?`<div class="hint">${esc(p.note)}</div>`:''}</article>`).join('')}
  function addLaborConfig(){const view=document.getElementById('view-config');if(!view||document.getElementById('repairLaborConfig'))return;const card=document.createElement('div');card.id='repairLaborConfig';card.className='card';const d=getData();card.innerHTML='<div class="section-title">Mano de obra por reparación</div><p class="muted">La cotización usa estos valores automáticamente. Solo modifica el campo de la cotización si un trabajo concreto requiere otro valor.</p><div class="grid two">'+Object.keys(repairLabor).map(k=>`<label>${esc(k)}<input type="number" min="0" step="1000" data-labor-repair="${esc(k)}" value="${Number(d.settings.laborByRepair?.[k]??repairLabor[k])}"></label>`).join('')+'</div><label>Mano de obra combinada<input id="bundleLabor" type="number" min="0" step="1000" value="'+Number(d.settings.bundleLabor||75000)+'"></label><button type="button" id="saveRepairLabor" class="secondary full">Guardar mano de obra</button>';view.appendChild(card);card.querySelector('#saveRepairLabor').onclick=()=>{const x=getData();x.settings=x.settings||{};x.settings.laborByRepair=x.settings.laborByRepair||{};card.querySelectorAll('[data-labor-repair]').forEach(e=>x.settings.laborByRepair[e.dataset.laborRepair]=Math.max(0,Number(e.value)||0));x.settings.bundleLabor=Math.max(0,Number(card.querySelector('#bundleLabor').value)||0);saveData(x);setCurrentLabor();renderQuoteSummary();alert('Base de mano de obra actualizada.')}}

  function patch(){
    seedRealData();buildMultiUI();addProviderTravelField();addLaborConfig();renderProvidersFixed();installReferenceEditors();
    const clear=document.getElementById('clearQuoteBtn');if(clear){clear.onclick=resetQuote;}
    const refForm=document.getElementById('referenceForm');refForm?.addEventListener('submit',e=>{const id=refForm.dataset.editId;if(!id)return;e.preventDefault();e.stopImmediatePropagation();const f=new FormData(refForm),d=getData(),r=d.references.find(x=>x.id===id),pid=String(f.get('provider')||'');if(!pid||!d.providers.some(p=>p.id===pid))return alert('Selecciona un proveedor válido.');r.brand=String(f.get('brand')).trim();r.model=String(f.get('model')).trim();r.repair=String(f.get('repair')).trim();r.quality=String(f.get('quality')||'').trim();r.providerId=pid;r.cost=Math.max(0,Number(f.get('cost'))||0);r.note=String(f.get('note')||'').trim();saveData(d);refForm.close();delete refForm.dataset.editId;renderProvidersFixed();alert('Referencia actualizada.');window.location.reload()},true);
    document.getElementById('newRefBtn')?.addEventListener('click',rebuildProviderSelect);
    ['quoteBrand','quoteModel','quoteRepair'].forEach(id=>document.getElementById(id)?.addEventListener('input',()=>setTimeout(()=>{const matches=currentMatchesFixed();if(!matches.some(r=>r.id===state.selectedReferenceId))state.selectedReferenceId=matches[0]?.id||'';const s=document.getElementById('quoteReference');if(s)s.value=state.selectedReferenceId;renderProviderComparisonFixed(matches);setCurrentLabor();renderQuoteSummary()},30)));
    document.getElementById('quoteRepair')?.addEventListener('change',()=>setTimeout(()=>{const matches=currentMatchesFixed();if(!matches.some(r=>r.id===state.selectedReferenceId))state.selectedReferenceId=matches[0]?.id||'';const s=document.getElementById('quoteReference');if(s)s.value=state.selectedReferenceId;renderProviderComparisonFixed(matches);setCurrentLabor();renderQuoteSummary()},30));
    document.getElementById('quoteReference')?.addEventListener('change',()=>setTimeout(()=>{renderProviderComparisonFixed(currentMatchesFixed());setCurrentLabor();renderQuoteSummary()},30));
    document.getElementById('laborCost')?.addEventListener('input',()=>setTimeout(renderQuoteSummary,20));
    window.renderProviderComparison=renderProviderComparisonFixed;
    const list=document.getElementById('referencesList');if(list)new MutationObserver(installReferenceEditors).observe(list,{childList:true,subtree:true});
    renderQuoteItems();renderProviderComparisonFixed(currentMatchesFixed());setCurrentLabor();renderQuoteSummary();
  }
  document.addEventListener('DOMContentLoaded',()=>setTimeout(patch,800));
})();
