/* V2.0.1 - Preservar configuración de mano de obra al guardar configuración general */
(function(){
  const KEY='bt-cotizador-v2';
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{
    const btn=document.getElementById('saveConfigBtn');
    if(!btn)return;
    btn.addEventListener('click',e=>{
      e.preventDefault();e.stopImmediatePropagation();
      let d;try{d=JSON.parse(localStorage.getItem(KEY))}catch{return}
      if(!d)return;
      d.settings=d.settings||{};
      d.settings.laborLow=Number(document.getElementById('laborLow')?.value)||0;
      d.settings.laborMedium=Number(document.getElementById('laborMedium')?.value)||0;
      d.settings.laborHigh=Number(document.getElementById('laborHigh')?.value)||0;
      d.settings.marginMin=Number(document.getElementById('marginMin')?.value)||0;
      d.settings.marginRec=Number(document.getElementById('marginRec')?.value)||0;
      d.settings.marginPrem=Number(document.getElementById('marginPrem')?.value)||0;
      d.settings.rounding=Number(document.getElementById('rounding')?.value)||1;
      localStorage.setItem(KEY,JSON.stringify(d));
      document.getElementById('laborCost')?.dispatchEvent(new Event('input',{bubbles:true}));
      alert('Configuración guardada sin borrar la base de mano de obra por reparación.');
    },true);
  },1000);
})();
