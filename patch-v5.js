/* V1.7 - Corrección de formulario + editor de referencias */
(function(){
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]));

  function fixQuoteVisibility(){
    const ref=document.getElementById('quoteReference');
    if(ref) ref.style.display='none';
    const card=ref?.closest('.card');
    if(card) card.style.display='block';
    const inputs=card?.querySelectorAll('input,select,label,#providerComparison,#referenceInfo,.quote-items,.quote-breakdown');
    inputs?.forEach(el=>{ if(el!==ref && el.style.display==='none') el.style.display=''; });
  }

  function addReferenceEditors(){
    const list=document.getElementById('referencesList');
    if(!list) return;
    list.querySelectorAll('.list-card').forEach(card=>{
      if(card.querySelector('.edit-reference')) return;
      const buttons=card.querySelectorAll('button[onclick]');
      let id=null;
      buttons.forEach(b=>{const m=(b.getAttribute('onclick')||'').match(/(?:useReference)\(['\"]([^'\"]+)/);if(m)id=m[1]});
      if(!id) return;
      const edit=document.createElement('button');
      edit.type='button'; edit.className='secondary edit-reference'; edit.textContent='Editar'; edit.dataset.refId=id;
      const row=document.createElement('div'); row.className='reference-actions';
      const cot=buttons[0]; if(cot){cot.parentElement?.replaceWith((()=>{const wrap=document.createElement('div');wrap.className='reference-actions';wrap.appendChild(cot);return wrap})());}
      const target=card.querySelector('.reference-actions')||card;
      target.appendChild(edit);
      edit.addEventListener('click',()=>openEdit(id));
    });
  }

  function openEdit(id){
    const r=data.references.find(x=>x.id===id); if(!r) return;
    const form=document.getElementById('referenceForm'); if(!form) return;
    form.dataset.editId=id;
    const title=form.querySelector('h2'); if(title) title.textContent='Editar referencia';
    const btn=form.querySelector('button[value="default"]'); if(btn) btn.textContent='Guardar cambios';
    form.elements.brand.value=r.brand; form.elements.model.value=r.model; form.elements.repair.value=r.repair;
    form.elements.quality.value=r.quality||''; form.elements.provider.value=r.providerId; form.elements.cost.value=r.cost; form.elements.note.value=r.note||'';
    document.getElementById('referenceDialog').showModal();
  }

  function handleEditSubmit(e){
    const form=e.target; const id=form?.dataset?.editId; if(!id) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const r=data.references.find(x=>x.id===id); if(!r) return;
    const f=new FormData(form);
    r.brand=String(f.get('brand')||'').trim(); r.model=String(f.get('model')||'').trim(); r.repair=String(f.get('repair')||'').trim();
    r.quality=String(f.get('quality')||'').trim(); r.providerId=f.get('provider'); r.cost=Math.max(0,Number(f.get('cost'))||0); r.note=String(f.get('note')||'').trim();
    save(); form.reset(); delete form.dataset.editId;
    const title=form.querySelector('h2'); if(title) title.textContent='Nueva referencia';
    const btn=form.querySelector('button[value="default"]'); if(btn) btn.textContent='Guardar referencia';
    document.getElementById('referenceDialog').close(); updateDatalists(); renderReferences(); updateQuoteReferences();
    if(typeof calculateAll==='function') calculateAll();
  }

  function editorStyles(){
    if(document.getElementById('v17-style'))return;
    const s=document.createElement('style'); s.id='v17-style';
    s.textContent=`
      #view-cotizador > .card:first-of-type{display:block!important}
      #view-cotizador > .card:first-of-type > .grid.two{margin-bottom:14px}
      #providerComparison:empty{display:none}
      .reference-actions{display:flex;gap:8px;align-items:center;margin-top:12px}
      .reference-actions button{flex:1}
      .edit-reference{margin:0!important;width:auto!important}
      .quote-item{box-shadow:0 2px 8px rgba(15,23,42,.04)}
      .smart-provider{font-weight:600}
      @media(max-width:700px){.reference-actions{display:grid;grid-template-columns:1fr 1fr}.reference-actions button{width:100%}}
    `; document.head.appendChild(s);
  }

  document.addEventListener('DOMContentLoaded',()=>{
    editorStyles();
    setTimeout(()=>{
      fixQuoteVisibility();
      const form=document.getElementById('referenceForm');
      form?.addEventListener('submit',handleEditSubmit,true);
      addReferenceEditors();
      const list=document.getElementById('referencesList');
      if(list){new MutationObserver(()=>addReferenceEditors()).observe(list,{childList:true,subtree:true});}
      const dialog=document.getElementById('referenceDialog');
      dialog?.addEventListener('close',()=>{if(form?.dataset?.editId){delete form.dataset.editId;const title=form.querySelector('h2');if(title)title.textContent='Nueva referencia';const btn=form.querySelector('button[value="default"]');if(btn)btn.textContent='Guardar referencia';}});
    },250);
  });
})();
