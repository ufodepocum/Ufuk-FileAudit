(() => {
 const form=document.getElementById('server-setup');if(!form)return;
 const buttons=[...form.querySelectorAll('[data-step]')],result=document.getElementById('setup-result');
 let discovered=false;
 form.addEventListener('submit',e=>e.preventDefault());
 buttons.forEach(button=>button.addEventListener('click',async()=>{
  if(!form.reportValidity())return;
  const data=new FormData(form);data.set('action',button.dataset.step);
  buttons.forEach(b=>b.disabled=true);result.textContent='İşlem sürüyor… Bu adım bitene kadar sayfayı kapatmayın.';
  try{
   const response=await fetch(form.dataset.url,{method:'POST',body:data,credentials:'same-origin',headers:{'X-CSRFToken':data.get('csrfmiddlewaretoken')}});
   if(response.redirected)throw new Error('Oturum sona erdi; tekrar giriş yapın.');
   let payload;try{payload=await response.json();}catch(e){throw new Error('Sunucu yanıtı alınamadı. Adımı yeniden denemeden önce sunucu durumunu kontrol edin.');}
   if(!response.ok)throw new Error(payload.error||'İşlem tamamlanamadı.');
   if(payload.details){
    const facts=document.getElementById('server-facts');facts.textContent=payload.details.computer+' · '+payload.details.os+' · Npcap: '+(payload.details.npcap?'Hazır':'Kurulum gerekli');
    const options=document.getElementById('share-options');options.querySelectorAll('label,p').forEach(n=>n.remove());options.hidden=false;
    payload.details.shares.forEach(share=>{
     const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.name='shares';input.value=share.Name;input.checked=payload.selected.includes(share.Name);
     label.append(input,document.createTextNode(' '+share.Name+' → '+share.Path));options.append(label);
    });
    discovered=true;result.textContent=payload.details.shares.length?'Paylaşımlar bulundu. İzlenecekleri işaretleyin; Npcap ve Windows bileşenleri adımlarını tamamlayın.':'Standart SMB paylaşımı bulunamadı. Önce Windows üzerinde bir paylaşım oluşturun.';
   }else result.textContent=payload.message;
   if(payload.reload){form.elements.password.value='';location.reload();}
  }catch(error){result.textContent=error.message;}
  finally{buttons.forEach(b=>b.disabled=b.dataset.step!=='inspect'&&!discovered);}
 }));
})();
