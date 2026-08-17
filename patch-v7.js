/* V1.9.1 - Datos reales de prueba Redmi 13 */
(function(){
  const KEY='bt-cotizador-v2';
  const uid=p=>p+Date.now().toString(36)+Math.random().toString(36).slice(2,7);
  function seed(){
    let d;try{d=JSON.parse(localStorage.getItem(KEY))}catch{return} if(!d)return;
    const p=d.providers?.find(x=>String(x.name||'').trim().toLowerCase()==='markboss repuestos');if(!p)return;
    const exists=d.references?.some(r=>String(r.brand).toLowerCase()==='xiaomi'&&String(r.model).toLowerCase()==='redmi 13'&&String(r.repair).toLowerCase()==='pantalla lcd'&&String(r.quality||'').toLowerCase()==='lcd con marco'&&r.providerId===p.id);
    if(!exists)d.references.push({id:uid('r'),brand:'Xiaomi',model:'Redmi 13',repair:'Pantalla LCD',quality:'LCD con marco',providerId:p.id,cost:38000,note:'Alternativa real de prueba: LCD con marco.'});
    localStorage.setItem(KEY,JSON.stringify(d));
  }
  document.addEventListener('DOMContentLoaded',()=>setTimeout(seed,900));
})();
