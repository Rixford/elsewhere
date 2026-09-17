(() => {
  'use strict';
  const capability=__CAPABILITY__;
  const motion=document.createElement('style');
  motion.textContent='*,*::before,*::after{animation-play-state:paused!important;transition:none!important}';
  document.head.append(motion);
  // Measurement only: no CSS resets, collision repairs, fake forms or navigation.
  function measure(){
    const width=innerWidth;
    parent.postMessage({elsewhere:true,capability,kind:'layout',width,overflow:document.documentElement.scrollWidth>width+2||document.body.scrollWidth>width+2,overflowing:[]},'*');
  }
  document.addEventListener('submit',e=>e.preventDefault());
  document.addEventListener('click',e=>{const link=e.target.closest('a');if(link){e.preventDefault();const anchor=link.dataset.anchor;if(anchor&&anchor!=='#')document.getElementById(anchor.slice(1))?.scrollIntoView();}});
  addEventListener('message',e=>{if(e.source===parent&&e.data?.capability===capability&&e.data.measure)measure();});
  addEventListener('load',()=>requestAnimationFrame(measure));
  addEventListener('resize',()=>requestAnimationFrame(measure));
})();
