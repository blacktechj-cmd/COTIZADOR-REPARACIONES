/* V1.2: correcciones del flujo de cotización, proveedores editables y mano de obra configurable. */
(function(){
  function money2(v){return new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));}
  function round2(v){const r=Number(data.settings.rounding)||1000;return Math.round(v/r)*r;}
  function esc2(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}

  window.btCalculate=function(){
    const refId=document.getElementById('quoteReference')?.value;
    const ref=data.references.find(r=>r.id===refId);
    const laborInput=document.getElementById('laborCost');
    const labor=Number(laborInput?.value)||0;
    const cost=Number(ref?.cost)||0;
    const base=cost+labor;
    const min=round2(base*(1+Number(data.settings.marginMin||0)/100));
    const rec=round2(base*(1+Number(data.settings.marginRec||0)/100));
    const prem=round2(base*(1+Number(data.settings.marginPrem||0)/100));
    document.getElementById('selectedCost').textContent=money2(base);
    document.getElementById('baseCost').value=money2(base);
    document.getElementById('priceMin').textContent=money2(min);
    document.getElementById('priceRecommended').textContent=money2(rec);
    document.getElementById('pricePremium').textContent=money2(prem);
  };

  window.btSelectReference=function(id){
    const r=data.references.find(x=>x.id===id); if(!r)return;
    document.getElementById('quoteReference').value=id;
    document.getElementById('quoteBrand').value=r.brand;
    document.getElementById('quoteModel').value=r.model;
    document.getElementById('quoteRepair').value=r.repair;
    renderProviderComparison();
    btCalculate();
    showView('cotizador');
    window.scrollTo({top:0,behavior:'smooth'});
  };

  function renderProviderComparison(){
    const box=document.getElementById('providerComparison'); if(!box)return;
    const brand=document.getElementById('quoteBrand').value.trim().toLowerCase();
    const model=document.getElementById('quoteModel').value.trim().toLowerCase();
    const repair=document.getElementById('quoteRepair').value;
    const matches=data.references.filter(r=>(!brand||r.brand.toLowerCase().includes(brand))&&(!model||r.model.toLowerCase().includes(model))&&(!repair||r.repair===repair));
    const hidden=document.getElementById('quoteReference');
    hidden.innerHTML='<option value="">Selecciona...</option>'+matches.map(r=>`<option value="${r.id}">${esc2(r.brand)} ${esc2(r.model)} · ${esc2(r.repair)}</option>`).join('');
    const selected=matches.find(r=>r.id===hidden.value);
    box.innerHTML=matches.length?matches.map(r=>{const p=data.providers.find(x=>x.id===r.providerId);const total=Number(r.cost)+(Number(p?.shipping)||0);const active=selected?.id===r.id?' selected-provider':'';return `<button type="button" class="provider-card${active}" data-ref-id="${r.id}"><div><strong>${esc2(p?.name||'Sin proveedor')}</strong><span>${esc2(p?.delivery||'')} ${p?.shipping?`· Envío ${money2(p.shipping)}`:''}</span></div><div><b>${money2(r.cost)}</b><small>Costo total ${money2(total)}</small></div></button>`}).join(''):'<div class="empty">No hay referencias guardadas para esta búsqueda.</div>';
    box.querySelectorAll('[data-ref-id]').forEach(b=>b.addEventListener('click',()=>{hidden.value=b.dataset.refId;renderProviderComparison();btCalculate();}));
    document.getElementById('referenceInfo').textContent=matches.length?`${matches.length} referencia(s) encontrada(s). Selecciona el proveedor que quieras usar.`:'No hay referencias guardadas para esta búsqueda. Puedes crear una desde “Referencias”.';
  }

  window.btEditProvider=function(id){
    const p=data.providers.find(x=>x.id===id);if(!p)return;
    const name=prompt('Nombre del proveedor:',p.name);if(name===null)return;
    const delivery=prompt('Tipo de entrega (Recogida presencial / Envío / Ambos):',p.delivery);if(delivery===null)return;
    const shipping=prompt('Costo de envío:',p.shipping||0);if(shipping===null)return;
    const note=prompt('Nota:',p.note||'');if(note===null)return;
    p.name=name.trim()||p.name;p.delivery=delivery.trim()||p.delivery;p.shipping=Number(shipping)||0;p.note=note.trim();save();renderProviders();renderProviderComparison();
  };

  function decorateProviders(){
    const list=document.getElementById('providersList');if(!list)return;
    list.querySelectorAll('.list-card').forEach((card,i)=>{
      const p=data.providers[i];if(!p||card.querySelector('.edit-provider'))return;
      const btn=document.createElement('button');btn.className='secondary full edit-provider';btn.textContent='Editar proveedor';btn.onclick=()=>btEditProvider(p.id);card.appendChild(btn);
    });
  }

  function initPatch(){
    data.settings.laborLow ??= 45000;
    data.settings.laborMedium ??= 55000;
    data.settings.laborHigh ??= 70000;
    data.settings.marginMin ??= 15;
    data.settings.marginRec ??= 30;
    data.settings.marginPrem ??= 45;
    const labor=document.getElementById('laborCost');
    const low=document.getElementById('laborLow'),med=document.getElementById('laborMedium'),high=document.getElementById('laborHigh');
    if(low)low.value=data.settings.laborLow;if(med)med.value=data.settings.laborMedium;if(high)high.value=data.settings.laborHigh;
    if(document.getElementById('marginMin'))document.getElementById('marginMin').value=data.settings.marginMin;
    if(document.getElementById('marginRec'))document.getElementById('marginRec').value=data.settings.marginRec;
    if(document.getElementById('marginPrem'))document.getElementById('marginPrem').value=data.settings.marginPrem;
    ['quoteBrand','quoteModel','quoteRepair'].forEach(id=>document.getElementById(id)?.addEventListener('input',()=>{renderProviderComparison();btCalculate();}));
    document.getElementById('quoteRepair')?.addEventListener('change',()=>{renderProviderComparison();btCalculate();});
    labor?.addEventListener('input',btCalculate);
    document.getElementById('referencesList')?.addEventListener('click',e=>{const b=e.target.closest('button[onclick^="useReference"]');if(b){e.preventDefault();const m=b.getAttribute('onclick').match(/'([^']+)'/);if(m)btSelectReference(m[1]);}});
    document.getElementById('newProviderBtn')?.addEventListener('click',()=>setTimeout(decorateProviders,50));
    document.querySelector('[data-view="proveedores"]')?.addEventListener('click',()=>setTimeout(decorateProviders,50));
    document.getElementById('saveConfigBtn')?.addEventListener('click',()=>{
      data.settings.laborLow=Number(low?.value)||45000;data.settings.laborMedium=Number(med?.value)||55000;data.settings.laborHigh=Number(high?.value)||70000;
      data.settings.marginMin=Number(document.getElementById('marginMin')?.value)||15;data.settings.marginRec=Number(document.getElementById('marginRec')?.value)||30;data.settings.marginPrem=Number(document.getElementById('marginPrem')?.value)||45;save();btCalculate();
    });
    if(document.getElementById('quoteReference')){renderProviderComparison();btCalculate();}
    setTimeout(decorateProviders,100);
  }
  document.addEventListener('DOMContentLoaded',initPatch);
})();
