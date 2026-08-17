/* V2.0.2 - Cálculo final: logística una sola vez por proveedor */
(function(){
  const KEY='bt-cotizador-v2';
  const money=v=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Math.round(Number(v)||0));
  const getData=()=>{try{return JSON.parse(localStorage.getItem(KEY))||null}catch{return null}};
  const round=(v,d)=>{const r=Number(d?.settings?.rounding)||1;return Math.round(v/r)*r};
  const laborFor=(r,d)=>Number(d?.settings?.laborByRepair?.[r]??d?.settings?.repairLabor?.[r]??({ 'Pantalla LCD':55000,'Pantalla OLED':65000,'Batería':40000,'Puerto de carga':60000,'Flex de Encendido/Volumen':35000,'Cámara Trasera':40000,'Cámara Frontal':35000,'Altavoz / Parlante':35000,'Micrófono':35000,'Placa Base (diagnóstico)':30000,'IC de carga / soldadura':80000,'Cambio de vidrio (glass)':70000,'Sensor de huella':45000,'Face ID / sensores':50000,'Limpieza interna':30000,'Flex Carga':45000})[r]??0);
  function providerCost(p){const shipping=Number(p?.shipping)||0;const travel=Number(p?.travelCost??p?.travel)||0;const trip=String(p?.delivery||'').toLowerCase().includes('recogida')?travel:0;return {shipping,travel:trip};}
  function calculateFinal(){
    const d=getData();if(!d)return;
    const refs=d.references||[],providers=d.providers||[];
    const articles=[...document.querySelectorAll('#quoteItems article.quote-item')];
    let parts=0,labor=0,items=[];
    if(articles.length){
      articles.forEach(a=>{
        const meta=[...a.querySelectorAll('.meta')];
        const info=(meta[1]?.textContent||'');
        const providerName=info.split(' · Repuesto')[0].trim();
        const match=providers.find(p=>String(p.name||'').trim()===providerName);
        const costMatch=info.match(/Repuesto\s*\$\s*([\d.]+)/i);
        const cost=costMatch?Number(costMatch[1].replace(/\./g,'')):0;
        parts+=cost;
        const input=a.querySelector('input[data-labor-index]');labor+=Number(input?.value)||0;
        items.push({provider:match});
      });
      if(articles.length>1)labor=Number(d.settings?.bundleLabor)||75000;
    }else{
      const id=document.getElementById('quoteReference')?.value||window.state?.selectedReferenceId;
      const r=refs.find(x=>x.id===id);
      if(r){
        parts=Number(r.cost)||0;
        const input=document.getElementById('laborCost');labor=Number(input?.value)||laborFor(r.repair,d);
        items=[{provider:providers.find(p=>p.id===r.providerId)}];
      }
    }
    const seen=new Set();let shipping=0,travel=0;
    items.forEach(it=>{const p=it.provider;if(!p||seen.has(p.id))return;seen.add(p.id);const c=providerCost(p);shipping+=c.shipping;travel+=c.travel});
    const base=parts+shipping+travel+labor;
    const min=round(base*(1+(Number(d.settings?.marginMin)||0)/100),d),rec=round(base*(1+(Number(d.settings?.marginRec)||0)/100),d),prem=round(base*(1+(Number(d.settings?.marginPrem)||0)/100),d);
    const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=money(v)};
    set('selectedCost',base);set('priceMin',min);set('priceRecommended',rec);set('pricePremium',prem);
    const b=document.getElementById('baseCost');if(b)b.value=money(base);
    const bd=document.getElementById('quoteBreakdown');if(bd)bd.innerHTML=base?`<div><span>Repuestos</span><strong>${money(parts)}</strong></div>${travel?`<div><span>Desplazamiento</span><strong>${money(travel)}</strong></div>`:''}${shipping?`<div><span>Envío</span><strong>${money(shipping)}</strong></div>`:''}<div><span>Mano de obra${articles.length>1?' combinada':''}</span><strong>${money(labor)}</strong></div><hr><div class="total-line"><span>Costo real</span><strong>${money(base)}</strong></div>`:'';
    if(articles.length>1){articles.forEach(a=>{const meta=[...a.querySelectorAll('.meta')][1];if(meta)meta.textContent=meta.textContent.replace(/\s*·\s*Desplazamiento\s*\$\s*[\d.]+/i,'')})}
  }
  function refresh(){setTimeout(calculateFinal,40)}
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{
    ['quoteBrand','quoteModel','quoteRepair','quoteReference','laborCost'].forEach(id=>document.getElementById(id)?.addEventListener('input',refresh));
    document.getElementById('quoteRepair')?.addEventListener('change',refresh);document.getElementById('quoteReference')?.addEventListener('change',refresh);
    document.getElementById('addRepairBtn')?.addEventListener('click',refresh);document.getElementById('clearQuoteBtn')?.addEventListener('click',refresh);
    const box=document.getElementById('quoteItems');if(box)new MutationObserver(refresh).observe(box,{childList:true,subtree:true,characterData:true});
    refresh();
  },1100));
})();
