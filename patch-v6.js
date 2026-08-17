/* V1.8 - Estado limpio + editor de referencias robusto */
(function(){
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  const repairDefaults={'Pantalla OLED':65000,'Pantalla LCD':55000,'Batería':40000,'Puerto de carga':60000,'Flex de Encendido/Volumen':35000,'Cámara Trasera':40000,'Cámara Frontal':35000,'Altavoz / Parlante':35000,'Micrófono':35000,'Placa Base (diagnóstico)':30000,'IC de carga / soldadura':80000,'Cambio de vidrio (glass)':70000,'Sensor de huella':45000,'Face ID / sensores':50000,'Limpieza interna':30000,'Flex Carga':45000};

  function rebuildProviderSelect(){
    const select=document.getElementById('dialogProvider'); if(!select)return;
    const current=select.value;
    select.innerHTML='<option value="">Selecciona un proveedor...</option>'+data.providers.map(p=>`<option value="${p.id}">${String(p.name||'Sin nombre').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]))}</option>`).join('');
    if(current && data.providers.some(p=>p.id===current))select.value=current;
  }

  function resetQuote(){
    if(typeof items!=='undefined') items=[];
    if(window.state) window.state.selectedReferenceId='';
    ['quoteBrand','quoteModel','laborCost','quoteReference'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=''});
    const repair=document.getElementById('quoteRepair'); if(repair)repair.value='';
    ['providerComparison','quoteItems','smartProvider','quoteBreakdown'].forEach(id=>{const e=document.getElementById(id);if(e)e.innerHTML=''});
    const info=document.getElementById('referenceInfo');if(info)info.textContent='Escribe marca y modelo para buscar referencias guardadas.';
    ['baseCost','selectedCost','partsCost','travelCostTotal','shippingCostTotal','laborTotal'].forEach(id=>{const e=document.getElementById(id);if(e){if('value' in e)e.value=money(0);e.textContent=money(0)}});
    ['priceMin','priceRecommended','pricePremium','priceFinal'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=money(0)});
    if(typeof renderItems==='function')renderItems();
  }

  function openNewReference(){
    const form=document.getElementById('referenceForm');if(!form)return;
    delete form.dataset.editId; form.reset();
    const title=form.querySelector('h2');if(title)title.textContent='Nueva referencia';
    const btn=form.querySelector('button[value="default"]');if(btn)btn.textContent='Guardar referencia';
    rebuildProviderSelect();
    document.getElementById('referenceDialog').showModal();
  }

  function openEditReference(id){
    const r=data.references.find(x=>x.id===id);if(!r)return;
    const form=document.getElementById('referenceForm');if(!form)return;
    form.dataset.editId=id;rebuildProviderSelect();
    form.elements.brand.value=r.brand||'';form.elements.model.value=r.model||'';form.elements.repair.value=r.repair||'';form.elements.quality.value=r.quality||'';form.elements.cost.value=Number(r.cost)||0;form.elements.note.value=r.note||'';
    const p=data.providers.find(x=>x.id===r.providerId);
    form.elements.provider.value=p?r.providerId:'';
    if(!p){
      const warn=document.getElementById('referenceProviderWarning')||document.createElement('div');warn.id='referenceProviderWarning';warn.className='form-warning';warn.textContent='Esta referencia tiene un proveedor que ya no existe. Selecciona uno nuevo antes de guardar.';form.querySelector('.modal-head')?.after(warn);
    } else document.getElementById('referenceProviderWarning')?.remove();
    const title=form.querySelector('h2');if(title)title.textContent='Editar referencia';
    const btn=form.querySelector('button[value="default"]');if(btn)btn.textContent='Guardar cambios';
    document.getElementById('referenceDialog').showModal();
  }

  function installReferenceButtons(){
    const list=document.getElementById('referencesList');if(!list)return;
    list.querySelectorAll('.list-card').forEach(card=>{
      const quote=card.querySelector('button[onclick*="useReference"]');if(!quote)return;
      if(card.querySelector('.edit-reference'))return;
      const match=(quote.getAttribute('onclick')||'').match(/useReference\(['\"]([^'\"]+)/);if(!match)return;
      const row=quote.closest('.price-row');if(!row)return;
      const edit=document.createElement('button');edit.type='button';edit.className='secondary edit-reference';edit.textContent='Editar';edit.addEventListener('click',()=>openEditReference(match[1]));
      row.appendChild(edit);
    });
  }

  function submitReference(e){
    const form=e.target;if(!form||form.id!=='referenceForm')return;
    const editId=form.dataset.editId;if(!editId)return;
    e.preventDefault();e.stopImmediatePropagation();
    const f=new FormData(form),brand=String(f.get('brand')||'').trim(),model=String(f.get('model')||'').trim(),repair=String(f.get('repair')||'').trim(),providerId=String(f.get('provider')||'');
    if(!brand||!model||!repair||!providerId||!data.providers.some(p=>p.id===providerId)){alert('Completa marca, modelo, reparación y selecciona un proveedor válido.');return}
    const r=data.references.find(x=>x.id===editId);if(!r)return;
    r.brand=brand;r.model=model;r.repair=repair;r.quality=String(f.get('quality')||'').trim();r.providerId=providerId;r.cost=Math.max(0,Number(f.get('cost'))||0);r.note=String(f.get('note')||'').trim();
    save();form.reset();delete form.dataset.editId;document.getElementById('referenceProviderWarning')?.remove();document.getElementById('referenceDialog').close();updateDatalists();renderReferences();updateQuoteReferences();
    if(typeof calculateAll==='function')calculateAll();
  }

  function addStyles(){
    if(document.getElementById('v18-style'))return;const s=document.createElement('style');s.id='v18-style';s.textContent=`
      .reference-actions{display:flex!important;gap:8px!important}.reference-actions .secondary{flex:1}.form-warning{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:10px;padding:10px;margin:10px 0;font-size:13px}
      #referenceDialog .modal{max-width:560px}.edit-reference{margin-left:8px!important}
    `;document.head.appendChild(s);
  }

  document.addEventListener('DOMContentLoaded',()=>{
    addStyles();
    setTimeout(()=>{
      // La cotización es temporal: al recargar debe comenzar vacía, pero se conservan referencias/proveedores/configuración.
      resetQuote();
      rebuildProviderSelect();
      const newBtn=document.getElementById('newRefBtn');if(newBtn){newBtn.onclick=openNewReference;}
      const form=document.getElementById('referenceForm');if(form)form.addEventListener('submit',submitReference,true);
      installReferenceButtons();
      const list=document.getElementById('referencesList');if(list)new MutationObserver(()=>installReferenceButtons()).observe(list,{childList:true,subtree:true});
      const dialog=document.getElementById('referenceDialog');if(dialog)dialog.addEventListener('close',()=>{document.getElementById('referenceProviderWarning')?.remove();if(form){delete form.dataset.editId;const title=form.querySelector('h2');if(title)title.textContent='Nueva referencia';const btn=form.querySelector('button[value="default"]');if(btn)btn.textContent='Guardar referencia';}});
    },500);
  });
})();
