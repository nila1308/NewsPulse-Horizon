(function(){
  const root=document.documentElement;
  const saved=localStorage.getItem('newspulse-theme');
  if(saved) root.setAttribute('data-theme',saved);
  const toggle=document.getElementById('themeToggle');
  const icon=document.getElementById('themeIcon');
  function updateIcon(){if(icon)icon.textContent=root.getAttribute('data-theme')==='dark'?'☀':'☾';}
  updateIcon();
  if(toggle) toggle.addEventListener('click',()=>{
    const next=root.getAttribute('data-theme')==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);localStorage.setItem('newspulse-theme',next);updateIcon();
  });
  const date=document.getElementById('todayDate');
  function updateBriefingClock(){
    if(!date) return;
    const now=new Date();
    const dateText=new Intl.DateTimeFormat('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Kolkata'}).format(now);
    const timeText=new Intl.DateTimeFormat('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true,timeZone:'Asia/Kolkata'}).format(now);
    date.textContent=dateText+' · '+timeText+' IST';
  }
  updateBriefingClock();
  setInterval(updateBriefingClock,60000);
  const topButton=document.getElementById('backToTop');
  if(topButton){window.addEventListener('scroll',()=>topButton.classList.toggle('visible',window.scrollY>420),{passive:true});topButton.addEventListener('click',()=>window.scrollTo({top:0,behavior:document.body.classList.contains('reduce-motion')?'auto':'smooth'}));}
  if(localStorage.getItem('newspulse-reduce-motion')==='1') document.body.classList.add('reduce-motion');
  const pass=document.getElementById('passwordInput'), eye=document.getElementById('passwordToggle');
  if(pass&&eye) eye.addEventListener('click',()=>{
    const show=pass.type==='password';pass.type=show?'text':'password';eye.setAttribute('aria-label',show?'Hide password':'Show password');eye.textContent=show?'◉':'◎';
  });
})();
