/* UI y limpieza estable. Este archivo es el único parche visual/limpieza. */
(function(){
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  function clearQuote(){
    const ids=['quoteBrand','quoteModel','quoteRepair','quoteReference','laborCost'];
    ids.forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
    if(window.state)window.state.selectedReferenceId='';
    const info=document.getElementById('referenceInfo');if(info)info.textContent='Escribe marca y modelo para buscar referencias guardadas.';
    const box=document.getElementById('providerComparison');if(box)box.innerHTML='';
    const base=document.getElementById('baseCost');if(base)base.value=money(0);
    ['selectedCost','priceMin','priceRecommended','pricePremium','priceFinal'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=money(0);});
    document.getElementById('quoteBrand')?.focus();
  }
  function visual(){
    if(document.getElementById('bt-clean-style'))return;
    const s=document.createElement('style');s.id='bt-clean-style';s.textContent='.clear-quote-v3{white-space:nowrap;border:1px solid #dbe1ea;background:#fff;color:#475569}.clear-quote-v3:hover{background:#f1f5f9}.provider-card{box-shadow:0 2px 8px rgba(15,23,42,.04)}.provider-card.selected-provider{border-color:#2563eb;background:#eff6ff}@media(max-width:700px){.clear-quote-v3{padding:9px 12px}}';document.head.appendChild(s);
  }
  document.addEventListener('DOMContentLoaded',()=>{
    visual();
    const b=document.getElementById('clearQuoteBtn');
    if(b&&!b.dataset.cleanV21){b.dataset.cleanV21='1';b.type='button';b.className='secondary clear-quote-v3';b.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();clearQuote();},true);}
  });
})();
