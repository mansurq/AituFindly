(() => {
 const markers=window.findlyMapConfig.markers || [];
 const ns='http://www.w3.org/2000/svg';
 const popup=document.getElementById('map-popup'), list=document.getElementById('map-popup-items');
 document.getElementById('close-popup').addEventListener('click',()=>{popup.hidden=true});
 let drawnSvg=null, drawnFloor=null;
 function show(items){
  list.replaceChildren();
  for(const item of items){
   const link=document.createElement('a'); link.href=item.url;link.target='_top';
   const title=document.createElement('strong');title.textContent=item.title;
   const place=document.createElement('small');place.textContent=item.location;
   link.append(title,place);list.append(link);
  }
  popup.hidden=false;
 }
 function draw(){
  const floor=Number(document.querySelector('.floor-option__button_current-floor')?.name?.slice(1)||1);
  const svg=[...document.querySelectorAll('svg')].find(s=>s.viewBox?.baseVal?.width>100 && s.querySelector('#WALLPAPER'));
  if(!svg)return;
  if(svg===drawnSvg && floor===drawnFloor && svg.querySelector('#findly-items-layer'))return;
  document.getElementById('findly-items-layer')?.remove();popup.hidden=true;
  drawnSvg=svg;drawnFloor=floor;
  const vb=svg.viewBox.baseVal, radius=Math.max(vb.width,vb.height)/65;
  const groups=[];
  for(const item of markers.filter(m=>m.floor===floor)){
   const group=groups.find(g=>Math.hypot((g.x-item.x)*vb.width,(g.y-item.y)*vb.height)<radius*2);
   if(group)group.items.push(item);else groups.push({x:item.x,y:item.y,items:[item]});
  }
  const layer=document.createElementNS(ns,'g');layer.id='findly-items-layer';
  for(const group of groups){
   const pin=document.createElementNS(ns,'g');pin.classList.add('findly-item-pin');pin.setAttribute('role','button');pin.setAttribute('tabindex','0');
   pin.setAttribute('aria-label',group.items.length===1?group.items[0].title:`Вещей в этом месте: ${group.items.length}`);
   const x=vb.x+group.x*vb.width,y=vb.y+group.y*vb.height;
   const circle=document.createElementNS(ns,'circle');
   for(const [k,v] of Object.entries({cx:x,cy:y,r:radius,fill:'#e84141',stroke:'#ffffff','stroke-width':radius/4}))circle.setAttribute(k,v);
   const text=document.createElementNS(ns,'text');
   for(const [k,v] of Object.entries({x,y:y+radius*.35,fill:'#fff','text-anchor':'middle','font-size':radius*1.05,'font-family':'system-ui','font-weight':'700','pointer-events':'none'}))text.setAttribute(k,v);
   text.textContent=group.items.length>1?String(group.items.length):'!';pin.append(circle,text);
   pin.addEventListener('click',e=>{e.stopPropagation();show(group.items)});
   pin.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show(group.items)}});
   layer.append(pin);
  }
  svg.append(layer);
 }
 new MutationObserver(draw).observe(document.getElementById('root'),{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
 draw();
})();
