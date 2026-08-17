/* V2.0.3 - Limpieza robusta del cotizador. Debe ejecutarse al final. */
(function(){
  function money(v){return new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0))}
  function clearQuoteHard(e){
    if(e){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation()}
    const ids=['quoteBrand','quoteModel','quoteRepair','quoteReference','laborCost'];
    ids.forEach(id=>{const el=document.getElementById(id);if(el){el.value='';el.dispatchEvent(new Event('change',{bubbles:false}))}});
    if(window.state)window.state.selectedReferenceId='';
    ['providerComparison','quoteItems','quoteBreakdown'].forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML=''})
    const info=document.getElementById('referenceInfo');if(info)info.textContent='Escribe marca y modelo para buscar referencias guardadas.';
    const base=document.getElementById('baseCost');if(base)base.value=money(0);
    ['selectedCost','priceMin','priceRecommended','pricePremium','priceFinal'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent=money(0)});
    document.querySelectorAll('#quoteItems input[data-labor-index]').forEach(el=>el.value='');
    document.getElementById('quoteBrand')?.focus();
  }
  function install(){
    const b=document.getElementById('clearQuoteBtn');
    if(!b)return;
    b.type='button';
    b.onclick=null;
    b.addEventListener('click',clearQuoteHard,true);
    b.addEventListener('pointerup',e=>{e.preventDefault();e.stopPropagation()},true);
  }
  document.addEventListener('DOMContentLoaded',()=>setTimeout(install,1300));
  new MutationObserver(()=>{const b=document.getElementById('clearQuoteBtn');if(b&&!b.dataset.v203){b.dataset.v203='1';install()}}).observe(document.documentElement,{childList:true,subtree:true});
})();
