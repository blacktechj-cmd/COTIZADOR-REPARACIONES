/* V1.6: experiencia visual y limpieza robusta de cotización. */
(function(){
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  function clearQuoteUI(){
    ['quoteBrand','quoteModel','laborCost','quoteReference'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
    const repair=document.getElementById('quoteRepair');if(repair)repair.value='';
    if(window.state) state.selectedReferenceId='';
    const info=document.getElementById('referenceInfo');if(info)info.textContent='Escribe marca y modelo para buscar referencias guardadas.';
    const box=document.getElementById('providerComparison');if(box)box.innerHTML='';
    const base=document.getElementById('baseCost');if(base)base.value=money(0);
    ['selectedCost','priceMin','priceRecommended','pricePremium','priceFinal'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=money(0);});
    document.getElementById('quoteBrand')?.focus();
  }
  function addClear(){
    if(document.getElementById('clearQuoteBtnV3'))return;
    const head=document.querySelector('#view-cotizador .page-head');if(!head)return;
    const b=document.createElement('button');b.id='clearQuoteBtnV3';b.type='button';b.className='secondary clear-quote-v3';b.innerHTML='↺ <span>Limpiar</span>';b.addEventListener('click',clearQuoteUI);head.appendChild(b);
  }
  function visual(){
    if(document.getElementById('bt-v16-styles'))return;
    const s=document.createElement('style');s.id='bt-v16-styles';s.textContent=`
      body{background:#f6f7fb}
      .topbar{background:linear-gradient(135deg,#111827,#1f2937);height:76px;padding:14px 24px}
      .brand{font-size:18px;letter-spacing:2px}.subtitle{color:#c7d0df}
      .app-shell{max-width:1080px;padding:28px 18px 110px}
      .page-head{margin-bottom:20px}.page-head h1{font-size:30px;letter-spacing:-.5px}.page-head p{font-size:14px}
      #view-cotizador .page-head{background:linear-gradient(135deg,#eff6ff,#ffffff);border:1px solid #dbeafe;border-radius:18px;padding:20px 22px}
      .card{border:1px solid #e5e7eb;border-radius:18px;box-shadow:0 8px 28px rgba(15,23,42,.06);padding:22px}
      #view-cotizador>.card:first-of-type{border-top:3px solid #2563eb}
      label{font-size:13px;color:#334155}input,select,textarea{border-color:#cbd5e1;border-radius:12px;background:#fff}
      .provider-comparison{margin-top:16px}.field-label{font-size:14px;margin:18px 0 8px;color:#172033}
      .provider-card{transition:.15s ease;box-shadow:0 2px 8px rgba(15,23,42,.04)}
      .provider-card:hover,.provider-option:hover{transform:translateY(-1px);box-shadow:0 5px 14px rgba(37,99,235,.12)}
      .results-card{border-top:0!important;background:linear-gradient(180deg,#fff,#fbfdff);padding-top:20px}
      .results-card .section-title{font-size:20px;margin-top:0}.result-grid{gap:12px}
      .result{min-height:112px;justify-content:center;border-radius:15px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.04)}
      .result span{font-weight:700}.result strong{font-size:24px}
      .result.recommended{border:2px solid #f59e0b;background:#fffbeb;box-shadow:0 5px 18px rgba(245,158,11,.12)}
      .result.recommended span{color:#92400e}.result.min{border-left:4px solid #22c55e}.result.premium{border-left:4px solid #ef4444}
      .cost-line{font-size:14px;background:#f8fafc;border-radius:12px;padding:14px;margin-top:14px;border-top:0}
      .clear-quote-v3{white-space:nowrap;border:1px solid #dbe1ea;background:#fff;color:#475569}.clear-quote-v3:hover{background:#f1f5f9}
      .primary{background:#2563eb;box-shadow:0 4px 10px rgba(37,99,235,.18)}.primary:hover{background:#1d4ed8}
      .bottom-nav{background:rgba(255,255,255,.96);backdrop-filter:blur(10px);border-top-color:#e2e8f0}.bottom-nav button{padding:6px 4px}.bottom-nav button.active{color:#2563eb}
      .list-card{border-radius:16px;box-shadow:0 4px 14px rgba(15,23,42,.04)}
      .price-row .secondary{padding:9px 13px}
      @media(max-width:700px){.app-shell{padding:16px 12px 105px}.page-head{align-items:flex-start}.page-head h1{font-size:24px}#view-cotizador .page-head{padding:17px}.clear-quote-v3{padding:9px 12px}.clear-quote-v3 span{display:none}.card{padding:16px}.result{min-height:92px}}
    `;document.head.appendChild(s);
  }
  function init(){visual();addClear();setTimeout(addClear,250);}
  document.addEventListener('DOMContentLoaded',init);
})();
