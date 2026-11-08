(() => {
 const frame=document.getElementById('campus-map');
 const floor=document.getElementById('map-floor'),x=document.getElementById('map-x'),y=document.getElementById('map-y');
 const label=document.getElementById('map-selection'), locationInput=document.getElementById('location');
 let automaticLocation='';
 window.addEventListener('message',e=>{
  if(e.origin!==location.origin || e.source!==frame.contentWindow || e.data?.type!=='findly-map-select')return;
  const d=e.data;
  if(![1,2,3].includes(d.floor) || ![d.x,d.y].every(v=>typeof v==='number' && Number.isFinite(v) && v>=0 && v<=1))return;
  floor.value=d.floor;x.value=d.x;y.value=d.y;
  const room=typeof d.room==='string'?d.room.slice(0,80):'';
  label.textContent=`Выбрано: этаж ${d.floor}${room?' · '+room:''}. Точка сохранится с объявлением.`;
  if(!locationInput.value || locationInput.value===automaticLocation){
   automaticLocation=room?`${room}, этаж ${d.floor}`:`AITU, этаж ${d.floor}`;
   locationInput.value=automaticLocation;
  }
 });
 document.getElementById('clear-map').addEventListener('click',()=>{
  floor.value=x.value=y.value='';label.textContent='Точка пока не выбрана.';
  if(locationInput.value===automaticLocation)locationInput.value='';
  automaticLocation='';frame.contentWindow.postMessage({type:'findly-map-clear'},location.origin);
 });
})();
