(() => {
  const config = window.findlyMapConfig;
  let selected = config.selected;
  const ns = 'http://www.w3.org/2000/svg';
  const currentFloor = () => Number(document.querySelector('.floor-option__button_current-floor')?.name?.slice(1) || 1);
  function mapSvg() {
    return [...document.querySelectorAll('svg')].find(svg => svg.viewBox?.baseVal?.width > 100 && svg.querySelector('#WALLPAPER'));
  }
  function draw() {
    const svg = mapSvg();
    const old = document.getElementById('findly-pin');
    if (!svg || !selected || currentFloor() !== selected.floor) { old?.remove(); return; }
    if (old && old.ownerSVGElement === svg) return;
    old?.remove();
    const vb = svg.viewBox.baseVal;
    const group = document.createElementNS(ns, 'g');
    group.id = 'findly-pin'; group.classList.add('findly-pin');
    const x = vb.x + selected.x * vb.width, y = vb.y + selected.y * vb.height;
    const radius = Math.max(vb.width, vb.height) / 65;
    const halo = document.createElementNS(ns, 'circle');
    for (const [k,v] of Object.entries({cx:x,cy:y,r:radius,fill:'#e84141',stroke:'#ffffff','stroke-width':radius/4})) halo.setAttribute(k,v);
    const dot = document.createElementNS(ns, 'circle');
    for (const [k,v] of Object.entries({cx:x,cy:y,r:radius/3,fill:'#ffffff'})) dot.setAttribute(k,v);
    group.append(halo, dot); svg.append(group);
  }
  let start;
  document.addEventListener('pointerdown', e => { start={x:e.clientX,y:e.clientY}; }, true);
  document.addEventListener('click', e => {
    if (config.readonly || !start || Math.hypot(e.clientX-start.x,e.clientY-start.y)>6) return;
    const svg=mapSvg();
    if (!svg || !svg.contains(e.target)) return;
    const matrix=svg.getScreenCTM(); if (!matrix) return;
    const point=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());
    const vb=svg.viewBox.baseVal;
    const x=(point.x-vb.x)/vb.width, y=(point.y-vb.y)/vb.height;
    if (x<0 || x>1 || y<0 || y>1) return;
    const room=e.target.closest('[data-name]')?.getAttribute('data-name') || '';
    selected={floor:currentFloor(),x,y,room};
    document.getElementById('findly-pin')?.remove(); draw();
    parent.postMessage({type:'findly-map-select',...selected},location.origin);
  }, true);
  window.addEventListener('message',e=>{
    if(e.origin!==location.origin || e.source!==parent || e.data?.type!=='findly-map-clear')return;
    selected=null;document.getElementById('findly-pin')?.remove();
  });
  let initialized=false;
  const observer=new MutationObserver(()=>{
    if(!initialized && document.querySelector('.floor-option__button')){
      initialized=true;
      if(selected)document.querySelector(`.floor-option__button[name="F${selected.floor}"]`)?.click();
    }
    draw();
  });
  observer.observe(document.getElementById('root'),{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
  draw();
})();
