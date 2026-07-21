// ── BOOT ──
(function(){
  var bar=document.getElementById('boot-fill');
  var steps=[{p:25,d:300},{p:50,d:600},{p:75,d:900},{p:100,d:1200}];
  steps.forEach(function(s){setTimeout(function(){bar.style.width=s.p+'%'},s.d)});
  setTimeout(function(){document.getElementById('boot').classList.add('hidden')},1500);
})();

// ── STATE
var SRV=window.location.origin,srvOnline=false,thinking=false,micActive=false,msgCount=0;
var currentVoice='vivian',currentLang='italian';
var recognition=null,SR=window.SpeechRecognition||window.webkitSpeechRecognition||null;
var msgsEl,spkbar,sendbtn,micbtn,minput,msgCountEl,logBox;

if(typeof marked!=='undefined'){marked.setOptions({breaks:true,gfm:true})}

// ── TOP TIME ──
function updateTopTime(){
  var el=document.getElementById('top-time');
  if(el)el.textContent=new Date().toLocaleTimeString('it',{hour:'2-digit',minute:'2-digit'});
}

// ── GLITCH BAR EFFECT ──
function triggerGlitch(){
  var bar=document.querySelector('.glitch-bar');
  if(!bar){
    bar=document.createElement('div');bar.className='glitch-bar';
    bar.style.cssText='position:fixed;height:2px;background:var(--pk);opacity:0;z-index:9995;pointer-events:none';
    document.body.appendChild(bar);
  }
  bar.style.top=(Math.random()*100)+'%';
  bar.style.left='0';
  bar.style.width=(20+Math.random()*40)+'%';
  bar.style.animation='none';
  void bar.offsetWidth;
  bar.style.animation='glitchBar 0.3s ease forwards';
}

// ── CLOCK ──
function tick(){
  var d=new Date();
  var p=function(n){return String(n).padStart(2,'0')};
  var days=['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY'];
  var mo=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];

  var el=document.getElementById('time-display');
  if(el)el.innerHTML=p(d.getHours())+':'+p(d.getMinutes())+'<span class="sec">'+p(d.getSeconds())+'</span>';

  document.getElementById('day-name').textContent=days[d.getDay()];
  document.getElementById('day-num').textContent=p(d.getDate());
  document.getElementById('month-name').textContent=mo[d.getMonth()];
  document.getElementById('year-num').textContent=d.getFullYear();

  updateTopTime();
  renderClocks(d);
}

function renderClocks(now){
  var zones=[
    {city:'BERLIN',tz:'Europe/Berlin'},
    {city:'NEW YORK',tz:'America/New_York'},
    {city:'TOKYO',tz:'Asia/Tokyo'},
    {city:'LONDON',tz:'Europe/London'},
    {city:'SYDNEY',tz:'Australia/Sydney'},
  ];
  var el=document.getElementById('clocks-list');
  if(!el)return;
  var html='';
  zones.forEach(function(z){
    var t=now.toLocaleTimeString('en-US',{timeZone:z.tz,hour:'2-digit',minute:'2-digit',hour12:false});
    html+='<div class="clock-item"><span class="clock-city">'+z.city+'</span><span class="clock-time">'+t+'</span></div>';
  });
  el.innerHTML=html;
}

// ── WEATHER ──
async function loadWeather(){
  try{
    var r=await fetch('https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,surface_pressure&timezone=Europe/Berlin');
    var d=await r.json();
    var c=d.current;
    document.getElementById('w-temp').innerHTML=Math.round(c.temperature_2m)+'<span class="unit">°</span>';
    document.getElementById('w-desc').textContent=c.weather_code+'';
    document.getElementById('w-hum').textContent=c.relative_humidity_2m+'%';
    document.getElementById('w-wind').textContent=Math.round(c.wind_speed_10m)+' km/h';
    document.getElementById('w-feels').textContent=Math.round(c.apparent_temperature)+'°';
    document.getElementById('w-press').textContent=Math.round(c.surface_pressure)+' hPa';

    var hum=c.relative_humidity_2m;
    document.getElementById('atmo-hum').textContent=hum+'%';
    document.getElementById('atmo-hum-bar').style.width=hum+'%';

    var icons={0:'☀️',1:'🌤️',2:'⛅',3:'☁️',45:'🌫️',48:'🌫️',51:'🌦️',53:'🌧️',55:'🌧️',61:'🌧️',63:'🌧️',65:'🌧️',71:'❄️',73:'❄️',75:'🌨️',80:'🌦️',81:'🌧️',82:'🌧️',95:'⛈️',96:'⛈️',99:'⛈️'};
    var descs={0:'Clear sky',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',45:'Foggy',48:'Rime fog',51:'Light drizzle',53:'Drizzle',55:'Heavy drizzle',61:'Light rain',63:'Rain',65:'Heavy rain',71:'Light snow',73:'Snow',75:'Heavy snow',80:'Light showers',81:'Showers',82:'Heavy showers',95:'Thunderstorm',96:'Thunderstorm with hail',99:'Severe thunderstorm'};
    document.getElementById('w-desc').textContent=(icons[c.weather_code]||'🌡️')+' '+(descs[c.weather_code]||'');
  }catch(e){
    document.getElementById('w-desc').textContent='OFFLINE';
  }
}

// ── SYSTEM INFO ──
async function loadSysInfo(){
  if(!srvOnline)return;
  try{
    var r=await fetch(SRV+'/api/sysinfo/detailed');var d=await r.json();
    var diskPct=parseInt((d.disk_pct||'0%').replace('%',''))||0;
    var battPct=parseInt((d.battery||'0%').replace('%',''))||0;

    document.getElementById('disk-fill').style.width=diskPct+'%';
    document.getElementById('disk-used').textContent=d.disk_used||'--';
    document.getElementById('disk-total').textContent=d.disk_total||'--';

    document.getElementById('power-pct').textContent=battPct+'%';
    document.getElementById('power-status').textContent=battPct>20?'ACTIVE':'LOW';
    var powerRing=document.getElementById('power-ring');
    if(powerRing){
      var circumference=2*Math.PI*18;
      powerRing.setAttribute('stroke-dashoffset',circumference*(1-battPct/100));
    }

    document.getElementById('waste-info').textContent=(d.processes||'--')+' processes';
    document.getElementById('uptime').textContent='UPTIME: '+(d.uptime||'--');
    document.getElementById('visual-label').textContent='CPU '+(d.cpu_usage||'0%')+' / RAM '+Math.round(100-(parseInt(d.ram_free)||70))+'%';
  }catch(e){}
}

// ── WAKE WORD STATUS ──
async function pollWakeStatus(){
  try{
    var r=await fetch(SRV+'/api/wake/status',{signal:AbortSignal.timeout(2000)});
    var d=await r.json();
    var on=d.wake===true;
    document.getElementById('wake-indicator').style.opacity=on?'1':'0.35';
    document.getElementById('wake-indicator').querySelector('span').textContent=on?'ON':'OFF';
    document.getElementById('mob-wake-indicator').style.opacity=on?'1':'0.35';
  }catch(e){}
}

function toggleWake(){
  var el=document.getElementById('wake-indicator');
  var on=el.style.opacity!=='1';
  fetch(SRV+'/api/wake/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:on})}).then(function(){pollWakeStatus()}).catch(function(){});
}

// ── PING ──
async function ping(){
  try{
    var r=await fetch(SRV+'/api/status',{signal:AbortSignal.timeout(3000)});
    var d=await r.json();srvOnline=true;
    document.getElementById('status-dot').className='dot online';
    document.getElementById('status-text').textContent='ONLINE';
    document.getElementById('top-model').textContent=d.model||'unknown';
    log('system online // '+d.model);
  }catch(e){
    srvOnline=false;
    document.getElementById('status-dot').className='dot offline';
    document.getElementById('status-text').textContent='OFFLINE';
  }
}

// ── VOICE ──
function selectVoice(el){
  document.querySelectorAll('.voice-btn').forEach(function(c){c.classList.remove('active')});
  el.classList.add('active');
  currentVoice=el.dataset.voice;
  log('voice: '+currentVoice);
  fetch(SRV+'/api/config/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qwen3_voice:currentVoice})}).catch(function(){});
}

// ── HOLOGRAM CANVAS ENGINE ──
var holoCanvas=null,holoCtx=null,holoAnimId=null;
var holoParticles=[],holoMouthOpen=0,holoEyeScan=0;
var mouthAnim=null;
var testFrame=0;
var holoThemeColors={cyberpunk:{c1:'#00f0ff',c2:'#ff00aa',c3:'#aa00ff'},holo:{c1:'#4ad8ff',c2:'#7ec8ff',c3:'#3aa0ff'},sunset:{c1:'#ff8800',c2:'#ff2255',c3:'#ff6600'},matrix:{c1:'#00ff41',c2:'#33ff77',c3:'#00ff88'},crystal:{c1:'#88ddff',c2:'#ff88cc',c3:'#c888ff'}};

function initHoloCanvas(){
  try{
    var c=document.getElementById('holo-canvas');
    if(!c||!c.parentElement){document.getElementById('mouth-debug').textContent='ERR: no canvas';return}
    holoCanvas=c;holoCtx=c.getContext('2d');
    if(!holoCtx){document.getElementById('mouth-debug').textContent='ERR: no context';return}
    resizeHoloCanvas();
    window.addEventListener('resize',resizeHoloCanvas);
    holoAnimId=requestAnimationFrame(renderHolo);
    document.getElementById('mouth-debug').textContent='started';
  }catch(e){document.getElementById('mouth-debug').textContent='init ERR:'+e.message}
}

function resizeHoloCanvas(){
  if(!holoCanvas)return;
  var parent=holoCanvas.parentElement;
  var rect=parent.getBoundingClientRect();
  holoCanvas.width=rect.width;
  holoCanvas.height=rect.height;
}

function initHoloParticles(){
  holoParticles=[];
  for(var i=0;i<80;i++){
    holoParticles.push({
      x:Math.random()*2-1, y:Math.random()*2-1, z:Math.random()*2-1,
      vx:(Math.random()-0.5)*0.003, vy:(Math.random()-0.5)*0.003, vz:(Math.random()-0.5)*0.003,
      size:1+Math.random()*2, phase:Math.random()*Math.PI*2
    });
  }
}

function getThemeColor(idx){
  var theme=localStorage.getItem('jarvis-theme')||'cyberpunk';
  var colors=holoThemeColors[theme]||holoThemeColors.cyberpunk;
  return idx===0?colors.c1:idx===1?colors.c2:colors.c3;
}

function bezierCurve(x0,y0,x1,y1,x2,y2,seg){
  var pts=[];
  for(var i=0;i<=seg;i++){
    var t=i/seg;
    var mt=1-t;
    var x=mt*mt*x0+2*mt*t*x1+t*t*x2;
    var y=mt*mt*y0+2*mt*t*y1+t*t*y2;
    pts.push({x:x,y:y});
  }
  return pts;
}

function drawNetworkParticles(ctx,particles,w,h,time,color1,color2){
  // Update and draw connections
  ctx.shadowBlur=0;
  for(var i=0;i<particles.length;i++){
    var p=particles[i];
    p.x+=p.vx+Math.sin(time*0.0005+p.phase)*0.001;
    p.y+=p.vy+Math.cos(time*0.0007+p.phase)*0.001;
    p.z+=p.vz+Math.sin(time*0.0003+p.phase*1.3)*0.001;
    if(p.x>1.2||p.x<-1.2){p.vx*=-1;p.x=Math.max(-1.2,Math.min(1.2,p.x))}
    if(p.y>1.2||p.y<-1.2){p.vy*=-1;p.y=Math.max(-1.2,Math.min(1.2,p.y))}
    if(p.z>1.2||p.z<-1.2){p.vz*=-1;p.z=Math.max(-1.2,Math.min(1.2,p.z))}
  }

  // Draw connections between nearby particles
  for(var i=0;i<particles.length;i++){
    for(var j=i+1;j<particles.length;j++){
      var a=particles[i],b=particles[j];
      var dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z;
      var dist=Math.sqrt(dx*dx+dy*dy+dz*dz);
      if(dist<0.35){
        var p1=project3D(a.x,a.y,a.z,w,h);
        var p2=project3D(b.x,b.y,b.z,w,h);
        var alpha=(1-dist/0.35)*0.15;
        ctx.strokeStyle=color1;ctx.globalAlpha=alpha;ctx.lineWidth=0.5;
        ctx.beginPath();ctx.moveTo(p1.x,p1.y);ctx.lineTo(p2.x,p2.y);ctx.stroke();
      }
    }
    ctx.globalAlpha=1;
  }

  // Draw particles
  particles.forEach(function(p){
    var proj=project3D(p.x,p.y,p.z,w,h);
    var size=p.size*proj.scale;
    var alpha=0.3+0.5*proj.scale;
    ctx.fillStyle=color1;ctx.globalAlpha=alpha;
    ctx.shadowColor=color1;ctx.shadowBlur=6;
    ctx.beginPath();ctx.arc(proj.x,proj.y,size,0,Math.PI*2);ctx.fill();
    ctx.shadowBlur=0;
  });
  ctx.globalAlpha=1;
}

function drawDataStreams(ctx,w,h,time,color){
  var count=12;
  ctx.shadowBlur=0;
  for(var i=0;i<count;i++){
    var x=w*(0.1+0.8*i/count);
    var speed=0.3+Math.sin(i*2.7)*0.15;
    var yOff=(time*0.0001*speed+i*0.7)%1;
    var len=0.1+Math.sin(i*1.3)*0.05;
    var segs=8;
    ctx.globalAlpha=0.08+Math.sin(time*0.0005+i)*0.04;
    for(var s=0;s<segs;s++){
      var sy=(yOff+s*len/segs)*h;
      var alpha=1-s/segs;
      var bw=0.5+Math.sin(time*0.002+i*2+s)*0.3;
      ctx.fillStyle=color;ctx.globalAlpha=alpha*0.15;
      ctx.fillRect(x-bw/2,sy,bw,2);
    }
  }
  ctx.globalAlpha=1;
}

function drawPulseRing(ctx,cx,cy,radius,time,color){
  var pulse=Math.sin(time*0.002)*0.3+0.4;
  ctx.strokeStyle=color;ctx.globalAlpha=0.08*pulse;
  ctx.lineWidth=1;ctx.shadowColor=color;ctx.shadowBlur=10;
  ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.stroke();
  ctx.globalAlpha=1;ctx.shadowBlur=0;
}

function renderHolo(time){
  try{
    if(!holoCtx||!holoCanvas)return;
    var ctx=holoCtx,w=holoCanvas.width,h=holoCanvas.height;
    ctx.clearRect(0,0,w,h);
    var cx=w/2,cy=h/2;
    var color1=getThemeColor(0),color2=getThemeColor(1);

    // Scanline
    ctx.globalAlpha=0.06;
    ctx.strokeStyle=color1;ctx.lineWidth=0.5;
    ctx.beginPath();ctx.moveTo(0,((time*0.00012)%1)*h);ctx.lineTo(w,((time*0.00012)%1)*h);ctx.stroke();
    ctx.globalAlpha=1;
  }catch(e){console.error('renderHolo:',e)}

  holoAnimId=requestAnimationFrame(renderHolo);
}

// ── WIDGET CANVAS (ologramma loading) ──
var widgetCanvas=null,widgetCtx=null,widgetAnimId=null;
var widgetParts=[],widgetTime=0;
var widgetVideoActive=false;
var widgetPhoto=null;

function initWidgetCanvas(){
  var c=document.getElementById('widget-canvas');
  if(!c)return;
  widgetCanvas=c;widgetCtx=c.getContext('2d');
  resizeWidgetCanvas();
  window.addEventListener('resize',resizeWidgetCanvas);
  widgetParts=[];
  for(var i=0;i<50;i++){
    widgetParts.push({
      x:Math.random(),y:Math.random(),
      vx:(Math.random()-0.5)*0.002,vy:(Math.random()-0.5)*0.002,
      size:1+Math.random()*2.5,
      phase:Math.random()*Math.PI*2,
      speed:0.3+Math.random()*0.7,
      spike:0,
      spikePhase:Math.random()*100
    });
  }
  // Carica foto per idle animation
  widgetPhoto=new Image();
  widgetPhoto.crossOrigin='anonymous';
  widgetPhoto.src='/holographic_avatar.png?v='+Date.now();
  widgetAnimId=requestAnimationFrame(renderWidget);
}

function resizeWidgetCanvas(){
  if(!widgetCanvas)return;
  var rect=widgetCanvas.parentElement.getBoundingClientRect();
  widgetCanvas.width=rect.width||420;
  widgetCanvas.height=rect.height||420;
}

function renderWidget(time){
  if(!widgetCtx||!widgetCanvas){widgetAnimId=requestAnimationFrame(renderWidget);return}
  try{
  widgetTime=time||performance.now();
  var ctx=widgetCtx,w=widgetCanvas.width,h=widgetCanvas.height;
  ctx.clearRect(0,0,w,h);
  var cx=w/2,cy=h/2;
  var color1=getThemeColor(0),color2=getThemeColor(1);
  var t=widgetTime*0.001;
  var isActive=holoState==='speaking'||holoState==='thinking';
  var intensity=isActive?1:0.35;

  if(!isActive){
    // ── IDLE: photo breathing ──
    drawIdlePhoto(ctx,w,h,cx,cy,t,color1);
  }else{
    // ── ACTIVE: neural animation ──
    drawNeuralAnim(ctx,w,h,cx,cy,t,color1,color2,intensity,holoState);
  }

  // ── Scanning line (sempre) ──
  var speedMul=isActive?1.8:0.6;
  var scanY=((t*0.08*speedMul)%2)*h;
  if(scanY>h)scanY=2*h-scanY;
  ctx.strokeStyle=color1;ctx.globalAlpha=0.03;ctx.lineWidth=0.5;
  ctx.shadowColor=color1;ctx.shadowBlur=4;
  ctx.beginPath();ctx.moveTo(0,scanY);ctx.lineTo(w,scanY);ctx.stroke();

  // ── Corner brackets ──
  var bracket=Math.min(w,h)*0.08;
  ctx.strokeStyle=color1;ctx.globalAlpha=0.1;ctx.lineWidth=0.5;
  ctx.shadowBlur=0;
  var corners=[[0,0,1,1],[w,0,-1,1],[0,h,1,-1],[w,h,-1,-1]];
  corners.forEach(function(c){
    ctx.beginPath();ctx.moveTo(c[0]+c[2]*bracket,c[1]);
    ctx.lineTo(c[0],c[1]);ctx.lineTo(c[0],c[1]+c[3]*bracket);
    ctx.stroke();
  });

  ctx.globalAlpha=1;ctx.shadowBlur=0;
  }catch(e){/* canvas error non-fatale: continua il loop */}
  widgetAnimId=requestAnimationFrame(renderWidget);
}

function drawIdlePhoto(ctx,w,h,cx,cy,t,color){
  if(!widgetPhoto||!widgetPhoto.complete||widgetPhoto.naturalWidth<1)return;
  var breathe=1+0.025*Math.sin(t*0.7);
  var glow=0.12+0.08*Math.sin(t*0.5);
  var dx=2*Math.sin(t*0.25);
  var dy=2*Math.cos(t*0.2);

  // Glow aura
  ctx.fillStyle=color;ctx.globalAlpha=glow;
  ctx.shadowColor=color;ctx.shadowBlur=50;
  ctx.beginPath();ctx.arc(cx+dx,cy+dy,Math.min(w,h)*0.35,0,Math.PI*2);ctx.fill();
  ctx.shadowBlur=0;

  // Photo
  var iw=widgetPhoto.naturalWidth,ih=widgetPhoto.naturalHeight;
  var ph=Math.min(w,h)*0.52*breathe;
  var pw=ph*iw/ih;
  if(pw>w*0.85){pw=w*0.85;ph=pw*ih/iw}
  ctx.drawImage(widgetPhoto,cx-pw/2+dx,cy-ph/2+dy,pw,ph);

  // Holographic tint
  ctx.fillStyle=color;ctx.globalAlpha=0.08;
  ctx.fillRect(0,0,w,h);

  // Pulsing rings (2)
  for(var i=0;i<2;i++){
    ctx.strokeStyle=color;ctx.globalAlpha=(0.06+0.04*Math.sin(t*0.5+i*2))*(1-i*0.3);
    ctx.lineWidth=0.5;ctx.shadowColor=color;ctx.shadowBlur=8;
    var ringR=Math.max(1,Math.min(w,h)*(0.28+0.08*i+0.04*Math.sin(t*0.4+i)));
    ctx.beginPath();ctx.arc(cx+dx,cy+dy,ringR,0,Math.PI*2);ctx.stroke();
  }
  ctx.shadowBlur=0;
  ctx.globalAlpha=1;
}

function drawNeuralAnim(ctx,w,h,cx,cy,t,color1,color2,intensity,state){
  var speedMul=state==='speaking'?2:1.5;

  // ── Neural spike train ──
  widgetParts.forEach(function(p){
    p.spike*=0.92;
    if(Math.random()<0.008*speedMul)p.spike=0.8+Math.random()*0.2;
  });

  // ── Pulsing rings ──
  for(var i=0;i<3;i++){
    var radius=Math.min(w,h)*(0.12+0.22*i+0.06*Math.sin(t*0.5*speedMul+i*2));
    var alpha=(0.06+0.05*Math.sin(t*0.6*speedMul+i*1.5))*intensity;
    ctx.strokeStyle=color1;ctx.globalAlpha=alpha;
    ctx.lineWidth=0.5+0.3*Math.sin(t*0.8*speedMul+i);
    ctx.shadowColor=color1;ctx.shadowBlur=8;
    ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.stroke();
  }

  // ── Targeting cross ──
  var crossR=Math.min(w,h)*0.06;
  ctx.strokeStyle=color1;ctx.globalAlpha=0.08*intensity;ctx.lineWidth=0.5;
  ctx.shadowBlur=0;
  ctx.beginPath();ctx.moveTo(cx-crossR,cy);ctx.lineTo(cx+crossR,cy);ctx.stroke();
  ctx.beginPath();ctx.moveTo(cx,cy-crossR);ctx.lineTo(cx,cy+crossR);ctx.stroke();

  // ── Move particles ──
  widgetParts.forEach(function(p){
    p.x+=p.vx*speedMul+Math.sin(t*0.3*speedMul+p.phase)*0.0005;
    p.y+=p.vy*speedMul+Math.cos(t*0.4*speedMul+p.phase*1.3)*0.0005;
    if(p.x>1.1||p.x<-0.1){p.vx*=-1;p.x=Math.max(-0.1,Math.min(1.1,p.x))}
    if(p.y>1.1||p.y<-0.1){p.vy*=-1;p.y=Math.max(-0.1,Math.min(1.1,p.y))}
  });

  // ── Neural connections ──
  var maxDist=0.3;
  for(var i=0;i<widgetParts.length;i++){
    for(var j=i+1;j<widgetParts.length;j++){
      var a=widgetParts[i],b=widgetParts[j];
      var dx=a.x-b.x,dy=a.y-b.y;
      var dist=Math.sqrt(dx*dx+dy*dy);
      if(dist<maxDist){
        var distNorm=1-dist/maxDist;
        var baseAlpha=distNorm*0.12*intensity;
        var fireAlpha=Math.max(a.spike,b.spike)*distNorm*0.4*speedMul;
        var finalAlpha=Math.min(baseAlpha+fireAlpha,0.5);
        ctx.strokeStyle=finalAlpha>0.2?color1:color2;
        ctx.globalAlpha=finalAlpha;
        ctx.lineWidth=finalAlpha>0.2?0.6:0.3;
        ctx.shadowColor=finalAlpha>0.2?color1:'transparent';
        ctx.shadowBlur=finalAlpha>0.2?6:0;
        ctx.beginPath();ctx.moveTo(a.x*w,a.y*h);ctx.lineTo(b.x*w,b.y*h);ctx.stroke();
      }
    }
  }

  // ── Draw particles ──
  widgetParts.forEach(function(p){
    var sz=p.size*(0.8+0.2*Math.sin(t*speedMul+p.phase*2));
    if(p.spike>0.1){
      var spikeSz=sz*(1+p.spike*3);
      ctx.fillStyle=color1;ctx.globalAlpha=p.spike*0.6;
      ctx.shadowColor=color1;ctx.shadowBlur=spikeSz*4;
      ctx.beginPath();ctx.arc(p.x*w,p.y*h,spikeSz,0,Math.PI*2);ctx.fill();
    }
    var alpha=Math.max(0.15+0.1*Math.sin(t*0.5*speedMul+p.phase),p.spike*0.4)*intensity;
    ctx.fillStyle=color1;ctx.globalAlpha=alpha;
    ctx.shadowColor=color1;ctx.shadowBlur=4;
    ctx.beginPath();ctx.arc(p.x*w,p.y*h,sz,0,Math.PI*2);ctx.fill();
  });
  ctx.globalAlpha=1;ctx.shadowBlur=0;

  // ── Status text ──
  var lines=state==='thinking'
    ?['⏳ UN ATTIMO...','ACCENDO I NEURONI']
    :['⚡ ACCENDENDO SINAPSI','GENERAZIONE VIDEO...'];
  var pulseAlpha=0.3+0.2*Math.sin(t*2*speedMul);
  ctx.textAlign='center';
  ctx.shadowColor=color1;ctx.shadowBlur=8;
  lines.forEach(function(l,i){
    ctx.fillStyle=color1;ctx.globalAlpha=pulseAlpha*(1-i*0.2);
    ctx.font=Math.min(w,h)*(0.032-i*0.005)+'px monospace';
    ctx.textBaseline=i===0?'bottom':'top';
    var yOff=i===0?-6-Math.min(w,h)*0.02:4+Math.min(w,h)*0.02;
    ctx.fillText(l,cx,cy+Math.min(w,h)*0.38+yOff);
  });
  ctx.globalAlpha=1;ctx.shadowBlur=0;
}

function toggleWidgetVideo(active){
  var wg=document.getElementById('avatar-widget');
  if(!wg)return;
  if(active){
    wg.classList.add('video-active');
  }else{
    wg.classList.remove('video-active');
  }
}

// ── THEME SELECTOR ──
function setHoloOverlay(){
  var o=document.getElementById('holo-overlay');
  if(o){o.classList.add('active')}
}

function selectTheme(el){
  var t=el.dataset.theme;
  document.querySelectorAll('.theme-btn').forEach(function(c){c.classList.remove('active')});
  el.classList.add('active');
  document.documentElement.className='theme-'+t;
  localStorage.setItem('jarvis-theme',t);
  setHoloOverlay();
  spawnParticles(t);
  triggerGlitch();
  var hst=document.getElementById('holo-status');
  if(hst){hst.textContent='✦ TEMPLATE: '+t.toUpperCase()+' ✦';hst.style.transition='opacity 0.3s';hst.style.opacity='1';setTimeout(function(){hst.style.opacity='0.3'},1500)}
  log('template: '+t);
}

function loadTheme(){
  var saved=localStorage.getItem('jarvis-theme')||'cyberpunk';
  var btn=document.querySelector('.theme-btn[data-theme="'+saved+'"]');
  if(btn){document.querySelectorAll('.theme-btn').forEach(function(c){c.classList.remove('active')});btn.classList.add('active')}
  document.documentElement.className='theme-'+saved;
  setHoloOverlay();
  spawnParticles(saved);
}

function spawnParticles(theme){
  var el=document.getElementById('particles');if(!el)return;
  el.innerHTML='';
  var confs={
    cyberpunk:{count:15,colors:['var(--cy)','var(--pk)','var(--pp)'],sz:[1,3],dur:[6,12],op:[0.2,0.4]},
    holo:{count:20,colors:['rgba(74,216,255,0.6)','rgba(126,200,255,0.4)','rgba(255,255,255,0.3)'],sz:[1,4],dur:[8,16],op:[0.15,0.35]},
    sunset:{count:18,colors:['var(--cy)','var(--pk)','var(--am)'],sz:[1,3],dur:[7,14],op:[0.2,0.4]},
    matrix:{count:25,colors:['rgba(0,255,65,0.5)'],sz:[1,2],dur:[5,10],op:[0.5,0.8]},
    crystal:{count:22,colors:['rgba(136,221,255,0.5)','rgba(255,255,255,0.3)','rgba(200,136,255,0.4)'],sz:[1,4],dur:[10,20],op:[0.15,0.3]}
  };
  var c=confs[theme]||confs.cyberpunk;
  for(var i=0;i<c.count;i++){
    var p=document.createElement('div');p.className='particle';
    var clr=c.colors[Math.floor(Math.random()*c.colors.length)];
    p.style.cssText='--sz:'+(c.sz[0]+Math.random()*(c.sz[1]-c.sz[0]))+'px;--dur:'+(c.dur[0]+Math.random()*(c.dur[1]-c.dur[0]))+'s;--del:'+Math.random()*5+'s;--op:'+(c.op[0]+Math.random()*(c.op[1]-c.op[0]))+';--px:'+((-50)+Math.random()*100)+'px;--px2:'+((-30)+Math.random()*60)+'px;background:'+clr+';box-shadow:0 0 6px '+clr+';left:'+Math.random()*100+'%;bottom:-10px';
    el.appendChild(p);
  }
}

// ── HOLO STATE ──
var widgetFloatTimer=null;
function playWaitingVideo(){
  if(window.Avatar3D)window.Avatar3D.setState('thinking');
}
function stopWaitingVideo(){
  if(window.Avatar3D)window.Avatar3D.setState('idle');
}
function setHoloState(state){
  holoState=state;
  var reactor=document.getElementById('cyber-reactor');
  var core=reactor?reactor.querySelector('.reactor-core'):null;
  var status=document.getElementById('holo-status');
  var wg=document.getElementById('avatar-widget');
  if(state==='thinking'){
    if(reactor)reactor.style.opacity='0.6';
    if(core){core.style.background='var(--am)';core.style.boxShadow='0 0 20px var(--amg),0 0 60px rgba(255,170,0,0.4)'}
    if(status){status.textContent='◉ PROCESSING...';status.className='thinking'}
    if(wg){wg.style.borderColor='rgba(255,170,0,0.3)';wg.style.boxShadow='0 0 20px rgba(255,170,0,0.12),inset 0 0 30px rgba(255,170,0,0.03)'}
    holoMouthOpen=0.2;holoEyeScan=0.6;
    if(window.Avatar3D)window.Avatar3D.setState('thinking');
  }else if(state==='speaking'){
    if(reactor)reactor.style.opacity='0.5';
    if(core){core.style.background='var(--cy)';core.style.boxShadow='0 0 20px var(--cyg),0 0 60px rgba(0,240,255,0.4)'}
    if(status){status.textContent='◉ SPEAKING...';status.className='speaking'}
    if(wg){wg.style.borderColor='rgba(0,240,255,0.4)';wg.style.boxShadow='0 0 30px rgba(0,240,255,0.15),inset 0 0 40px rgba(0,240,255,0.04)'}
    holoMouthOpen=1;holoEyeScan=0.3;
    if(window.Avatar3D)window.Avatar3D.setState('speaking');
    if(wg&&!widgetFloatTimer){
      widgetFloat(wg);
    }
  }else{
    if(reactor)reactor.style.opacity='var(--reactor-bg,0.35)';
    if(core){core.style.background='var(--cy)';core.style.boxShadow='0 0 20px var(--cyg),0 0 60px rgba(0,240,255,0.2)'}
    if(status){status.textContent='◆ SYSTEM STANDBY ◆';status.className='idle'}
    if(wg){wg.style.borderColor='rgba(0,240,255,0.2)';wg.style.boxShadow='0 0 20px rgba(0,240,255,0.08),inset 0 0 30px rgba(0,240,255,0.02)';resetWidgetPos(wg)}
    holoMouthOpen=0;holoEyeScan=0;
    if(mouthAnim){clearInterval(mouthAnim);mouthAnim=null}
    if(widgetFloatTimer){clearInterval(widgetFloatTimer);widgetFloatTimer=null}
    if(window.Avatar3D)window.Avatar3D.setState('idle');
  }
}

function widgetFloat(wg){
  var positions=[
    function(){return{left:'50%',top:'30%',transform:'translate(-50%,-50%)',right:'auto',bottom:'auto'}},
    function(){return{left:'12px',top:'12px',right:'auto',bottom:'auto',transform:'none'}},
    function(){return{right:'12px',top:'50%',transform:'translateY(-50%)',left:'auto',bottom:'auto'}},
    function(){return{left:'35%',top:'10px',right:'auto',bottom:'auto',transform:'none'}},
    function(){return{right:'25%',top:'40%',transform:'translateY(-50%)',left:'auto',bottom:'auto'}},
    function(){return{left:'12px',top:'55%',transform:'translateY(-50%)',right:'auto',bottom:'auto'}},
    function(){return{left:'50%',top:'12px',transform:'translateX(-50%)',right:'auto',bottom:'auto'}},
  ];
  var i=0;
  var p=positions[0]();
  Object.assign(wg.style,p);
  i=1;
  widgetFloatTimer=setInterval(function(){
    var p=positions[i%positions.length]();
    Object.assign(wg.style,p);
    i++;
  },3500);
}

function resetWidgetPos(wg){
  wg.style.left='50%';wg.style.top='50%';wg.style.right='auto';wg.style.bottom='auto';
  wg.style.transform='translate(-50%,-50%)';
}

function testMouth(){
  if(mouthAnim){clearInterval(mouthAnim);mouthAnim=null}
  setHoloState('speaking');
  setTimeout(function(){setHoloState('idle')},3000);
}

// ── CHAT ──
function ts(){return new Date().toLocaleTimeString('it',{hour:'2-digit',minute:'2-digit'})}

function log(m){
  var el=document.getElementById('log-box');if(!el)return;
  var t=new Date().toLocaleTimeString('it',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  el.innerHTML+='<div class="log-entry">['+t+'] '+m+'</div>';
  el.scrollTop=el.scrollHeight;
  if(el.children.length>100)el.innerHTML=el.innerHTML.slice(-5000);
}

function sysmsg(t){
  if(!msgsEl)return;
  var d=document.createElement('div');d.className='sysmsg';d.textContent='── '+t+' ──';
  msgsEl.appendChild(d);msgsEl.scrollTop=msgsEl.scrollHeight;log(t);
}

function usermsg(t){
  if(!msgsEl)return;
  var d=document.createElement('div');d.className='msg';
  d.innerHTML='<div class="msg-header"><div class="msg-avatar user">U</div><span class="msg-name user">YOU</span><span class="msg-time">'+ts()+'</span></div><div class="msg-body user-msg">'+esc(t)+'</div>';
  msgsEl.appendChild(d);msgsEl.scrollTop=msgsEl.scrollHeight;
}

// ── WEBCAM ──
var webcamYTPlayer=null,webcamYTLoaded=false;
var webcamSources={
  'tokyo':['8H3nRCFVR6Y','Shibuya Scramble'],
  'shibuya':['8H3nRCFVR6Y','Shibuya Crossing'],
  'shinjuku':['8H3nRCFVR6Y','Shinjuku Kabukicho'],
  'roma':['54_skPGLNhA','Roma Colosseo'],
  'rome':['54_skPGLNhA','Rome Colosseum'],
  'new york':['VGnFLdQW39A','Times Square NYC'],
  'new york city':['VGnFLdQW39A','Times Square NYC'],
  'nyc':['VGnFLdQW39A','Times Square NYC'],
  'londra':['WKGK_hYnlGE','London Live'],
  'london':['WKGK_hYnlGE','London Live'],
  'parigi':['QcOYSVrPCAc','Paris Eiffel Tower'],
  'paris':['QcOYSVrPCAc','Paris Eiffel Tower'],
  'berlin':['iaTAp8FxtHw','Berlin Frankfurter Tor Live'],
  'berlino':['iaTAp8FxtHw','Berlino Frankfurter Tor Live'],
  'milano':['28BXLXTP63E','Milano Duomo Live'],
  'milan':['28BXLXTP63E','Milan Duomo Live'],
  'venezia':['CMn6xQXuSjI','Venezia Canal Grande'],
  'venice':['CMn6xQXuSjI','Venice Grand Canal'],
  'dubai':['Q7h0D-Fu20k','Dubai Marina'],
  'barcellona':['1Zd10zOj628','Barcelona Beach'],
  'barcelona':['1Zd10zOj628','Barcelona Beach'],
  'bibione':['__EMBED__https://services.whatsupcams.com/wgt/it_bibione09/','Bibione Spiaggia Live'],
  'jesolo':['1-6FHrCJKtA','Jesolo Spiaggia Live'],
};

function loadYTAPI(){
  if(webcamYTLoaded||window.YT)return;
  var tag=document.createElement('script');
  tag.src='https://www.youtube.com/iframe_api';
  var first=document.getElementsByTagName('script')[0];
  first.parentNode.insertBefore(tag,first);
}

function openWebcam(city, lat, lon, video_id){
  closeWebcam();
  var w=document.getElementById('webcam-widget');
  var t=document.getElementById('webcam-title');
  var c=document.getElementById('webcam-city');
  var s=document.getElementById('webcam-status');
  if(!w)return;
  var cityLower=city.toLowerCase();
  var src=webcamSources[cityLower];
  if(!src){
    var keys=Object.keys(webcamSources);
    for(var i=0;i<keys.length;i++){
      if(cityLower.includes(keys[i])||keys[i].includes(cityLower)){src=webcamSources[keys[i]];break}
    }
  }
  c.textContent=city.toUpperCase();
  s.textContent='\u25CF LIVE';
  w.classList.remove('hidden');
  var vid=src?src[0]:video_id;
  if(vid){
    if(t)t.textContent='📡 '+(src?src[1]:city);
    playYT(vid);
  }else{
    if(t)t.textContent='📡 '+city+' WEBCAM';
    var f=document.getElementById('webcam-iframe');
    if(f){
      f.innerHTML='';
      var ifr=document.createElement('iframe');
      ifr.src='https://www.youtube.com/embed?listType=search&list='+encodeURIComponent(city+' live webcam 4k')+'&autoplay=1&mute=1&controls=0';
      ifr.style.cssText='width:100%;height:100%;border:none';
      ifr.setAttribute('allow','autoplay; encrypted-media; picture-in-picture');
      ifr.setAttribute('allowfullscreen','');
      f.appendChild(ifr);
    }
  }
  log('webcam: '+city);
}

function playYT(videoId){
  var body=document.getElementById('webcam-body');
  var f=document.getElementById('webcam-iframe');
  if(!f||!body)return;
  f.innerHTML='';
  if(typeof videoId==='string'&&videoId.startsWith('__EMBED__')){
    var embedUrl=videoId.slice(9);
    var ifr=document.createElement('iframe');
    ifr.src=embedUrl;
    ifr.style.cssText='width:100%;height:100%;border:none';
    ifr.setAttribute('allow','autoplay; encrypted-media; picture-in-picture');
    ifr.setAttribute('allowfullscreen','');
    f.appendChild(ifr);
    return;
  }
  loadYTAPI();
  if(typeof YT!=='undefined'&&YT.Player){
    if(webcamYTPlayer&&webcamYTPlayer.destroy)webcamYTPlayer.destroy();
    webcamYTPlayer=new YT.Player(f,{
      height:'100%',width:'100%',
      videoId:videoId,
      playerVars:{autoplay:1,mute:1,controls:0,rel:0,modestbranding:1},
      events:{
        onReady:function(e){e.target.mute();e.target.playVideo();},
        onError:function(){
          f.innerHTML='';
          var ifr=document.createElement('iframe');
          ifr.src='https://www.youtube.com/embed/'+videoId+'?autoplay=1&mute=1&controls=0';
          ifr.style.cssText='width:100%;height:100%;border:none';
          f.appendChild(ifr);
        }
      }
    });
  }else{
    var ifr=document.createElement('iframe');
    ifr.src='https://www.youtube.com/embed/'+videoId+'?autoplay=1&mute=1&controls=0&rel=0&modestbranding=1';
    ifr.style.cssText='width:100%;height:100%;border:none';
    ifr.setAttribute('allow','autoplay; encrypted-media; picture-in-picture');
    ifr.setAttribute('allowfullscreen','');
    f.appendChild(ifr);
  }
}

function closeWebcam(){
  var w=document.getElementById('webcam-widget');
  var f=document.getElementById('webcam-iframe');
  if(w)w.classList.add('hidden');
  if(webcamYTPlayer&&webcamYTPlayer.destroy){try{webcamYTPlayer.destroy()}catch(e){}webcamYTPlayer=null}
  if(f)f.innerHTML='';
}

// ── WEBCAM GRID ──
function openWebcamGrid(cities){
  var w=document.getElementById('webcam-grid-widget');
  var b=document.getElementById('webcam-grid-body');
  if(!w||!b)return;
  w.classList.remove('hidden');
  b.innerHTML='';
  cities.forEach(function(c){
    var card=document.createElement('div');card.className='wc-grid-card';
    var hdr=document.createElement('div');hdr.className='wc-grid-card-header';
    hdr.textContent=c.name;
    var body=document.createElement('div');body.className='wc-grid-card-body';
    var vid=c.video_id;
    // Se il server non ha trovato video, cerca nella mappa hardcoded
    if(!vid){
      var m=webcamSources[c.name.toLowerCase()]||webcamSources[c.name.split(' ')[0].toLowerCase()];
      if(m&&m[0]&&!m[0].startsWith('__EMBED__'))vid=m[0];
      if(m&&m[0]&&m[0].startsWith('__EMBED__'))vid=m[0];
    }
    if(vid){
      if(typeof vid==='string'&&vid.startsWith('__EMBED__')){
        var embedUrl=vid.slice(9);
        var ifr=document.createElement('iframe');
        ifr.src=embedUrl;
        ifr.style.cssText='width:100%;height:100%;border:none';
        ifr.setAttribute('allow','autoplay; encrypted-media; picture-in-picture');
        ifr.setAttribute('allowfullscreen','');
        body.appendChild(ifr);
      }else{
        var ifr=document.createElement('iframe');
        ifr.src='https://www.youtube.com/embed/'+vid+'?autoplay=1&mute=1&loop=1&controls=0&rel=0';
        ifr.setAttribute('allow','autoplay; encrypted-media; picture-in-picture');
        ifr.setAttribute('allowfullscreen','');
        body.appendChild(ifr);
      }
    }else{
      body.innerHTML='<div class="no-vid">📡 '+c.name+'<br><span style="color:var(--tx4);font-size:8px">'+c.lat.toFixed(4)+', '+c.lon.toFixed(4)+'</span><br><span style="color:var(--tx3);margin-top:4px">Nessuna live trovata</span></div>';
    }
    card.appendChild(hdr);card.appendChild(body);b.appendChild(card);
  });
}

function closeWebcamGrid(){
  var w=document.getElementById('webcam-grid-widget');
  var b=document.getElementById('webcam-grid-body');
  if(w)w.classList.add('hidden');
  if(b)b.innerHTML='';
}

function openHAWidget(){
  var w=document.getElementById('ha-widget');
  var f=document.getElementById('ha-widget-iframe');
  if(w)w.classList.remove('hidden');
  if(f)f.src='https://mikweb.info';
}
function closeHAWidget(){
  var w=document.getElementById('ha-widget');
  var f=document.getElementById('ha-widget-iframe');
  if(w)w.classList.add('hidden');
  if(f)f.src='';
}

function weatherCardHTML(d){
  var icons={0:'☀️',1:'🌤️',2:'⛅',3:'☁️',45:'🌫️',48:'🌫️',51:'🌦️',55:'🌦️',61:'🌧️',65:'🌧️',71:'❄️',77:'❄️',80:'🌦️',82:'🌦️',95:'⛈️',99:'⛈️'};
  function wico(c){return icons[c]||(c>=51&&c<=55?'🌦️':c>=61&&c<=65?'🌧️':c>=71&&c<=77?'❄️':c>=80&&c<=82?'🌦️':c>=95?'⛈️':'❓')}
  if(d.today){
    var t=d.today;
    return '<div class="weather-card"><div class="wc-header">'+esc(d.city)+' <span class="wc-label">'+esc(d.label)+'</span></div><div class="wc-main"><div class="wc-icon">'+wico(t.code)+'</div><div class="wc-temps"><div class="wc-temp-max">'+t.temp_max+'°</div><div class="wc-temp-min">'+t.temp_min+'°</div></div><div class="wc-detail"><div class="wc-desc">'+esc(t.desc)+'</div><div class="wc-wind">💨 '+t.wind+' km/h</div></div></div></div>';
  }
  if(d.forecast){
    var items=d.forecast.map(function(f){
      return '<div class="wc-day"><div class="wc-dayname">'+esc(f.day)+'</div><div class="wc-dayicon">'+wico(f.code)+'</div><div class="wc-desc-sm">'+esc(f.desc.split(',')[0])+'</div><div class="wc-daytemps"><span class="wc-daymax">'+f.temp_max+'°</span> <span class="wc-daymin">'+f.temp_min+'°</span></div></div>';
    }).join('');
    return '<div class="weather-card"><div class="wc-header">'+esc(d.city)+' <span class="wc-label">'+esc(d.label)+'</span></div><div class="wc-week">'+items+'</div></div>';
  }
  return '';
}

// botmsg è definita più avanti con supporto IMAGE — questa è rimossa per evitare duplicati
function showThinking(){var el=document.getElementById('thinkEl');if(el)el.classList.add('active')}

async function speak(text){
  if(!text||!srvOnline)return;
  var clean=text.replace(/\*\*(.+?)\*\*/g,'$1').replace(/\*(.+?)\*/g,'$1').replace(/<[^>]+>/g,'').replace(/#{1,6}\s*/g,'').replace(/`([^`]+)`/g,'$1').trim();
  if(!clean)return;
  var wg=document.getElementById('avatar-widget');
  if(wg)wg.classList.add('speaking');
  if(spkbar)spkbar.innerHTML='<div class="wave"><span></span><span></span><span></span><span></span><span></span></div> SYNTHESIZING...';
  try{
    var r=await fetch(SRV+'/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:clean,voice:currentVoice,language:currentLang})});
    if(!r.ok)throw new Error('HTTP '+r.status);
    var blob=await r.blob();
    if(spkbar)spkbar.innerHTML='<div class="wave"><span></span><span></span><span></span><span></span><span></span></div> SPEAKING';
    setHoloState('speaking');
    var done=function(){if(spkbar)spkbar.innerHTML='';if(wg)wg.classList.remove('speaking');setHoloState('idle')};
    if(window.Avatar3D){
      try{ await window.Avatar3D.speak(blob,done); return; }
      catch(e){ log('avatar3d.speak: '+e.message) }
    }
    var url=URL.createObjectURL(blob);
    var audio=new Audio(url);
    audio.onended=function(){URL.revokeObjectURL(url);done()};
    audio.onerror=function(){URL.revokeObjectURL(url);done()};
    audio.play().catch(done);
  }catch(e){if(spkbar)spkbar.innerHTML='';if(wg)wg.classList.remove('speaking');log('tts: '+e.message);setHoloState('idle')}
}

function send(){
  var text=minput?minput.value.trim():'';
  if(!text||thinking)return;
  if(minput)minput.value='';
  doChat(text);
}

async function doChat(text){
  if(thinking)return;
  if(!srvOnline){sysmsg('server offline');return}
  thinking=true;usermsg(text);showThinking();setHoloState('thinking');
  var t0=Date.now();
  try{
    var r=await fetch(SRV+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    if(!r.ok)throw new Error('HTTP '+r.status);
    var d=await r.json();if(d.error)throw new Error(d.error);
    var elapsed=((Date.now()-t0)/1000).toFixed(2);
    // Se reply vuoto ma ci sono actions, usa '' (botmsg mostrerà badge + immagini)
    // Se reply E actions entrambi vuoti, non aggiungere messaggio fantasma
    var hasActions=(d.actions||[]).filter(function(a){return !a.startsWith('SPEECH:')}).length>0;
    if((d.reply||'').trim()!=='' || hasActions){
      botmsg(d.reply||'',d.actions||[]);
    }
    if(d.model)showTierBadge(!!d.fast,d.model.replace('llama-','').replace('-versatile','').replace('-instant','⚡'));
    document.getElementById('latbar').textContent='LAT '+elapsed+'s';
    log('response '+elapsed+'s // model: '+(d.model||'groq'));
    triggerGlitch();
    await speak(d.reply||'');
  }catch(e){
    var th=document.getElementById('thinkEl');if(th)th.classList.remove('active');
    botmsg('error: '+e.message,[]);log('error: '+e.message);setHoloState('idle');
  }
  thinking=false;if(minput)minput.focus();
  if(holoState!=='speaking')setHoloState('idle');
}

async function qa(tool,args){
  if(!srvOnline){sysmsg('server offline');return}
  try{
    var r=await fetch(SRV+'/api/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:tool,args:args})});
    var d=await r.json();sysmsg(d.result||d.error||'ok');log(tool+': '+(d.result||d.error));
  }catch(e){sysmsg('error: '+e.message)}
}

async function mailAction(){
  if(!srvOnline){sysmsg('server offline');return}
  try{
    var r=await fetch(SRV+'/api/mail/unread',{method:'GET'});
    var d=await r.json();
    var msg=d.unread||'📬 Nessuna email';
    sysmsg(msg);
    log('mail count: '+msg);
    if(msg.includes('Nessuna'))return;
    var count=d.count||0;
    speak(msg);
    if(confirm('📬 '+msg.replace('📬 ','')+'. Vuoi che te le legga?')){
      sysmsg('lettura email...');
      var r2=await fetch(SRV+'/api/mail/recent',{method:'GET'});
      var d2=await r2.json();
      var emails=d2.emails_text||'';
      if(emails){
        sysmsg(emails.replace(/\n/g,' | ').substring(0,200)+'...');
        speak(emails);
        log('mail read aloud');
      }
    } else {
      sysmsg('ok, non leggo le email');
    }
  }catch(e){sysmsg('error: '+e.message)}
}

async function speakAction(tool,args){
  if(!srvOnline){sysmsg('server offline');return}
  try{
    var r=await fetch(SRV+'/api/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:tool,args:args})});
    var d=await r.json();var result=d.result||d.error||'ok';
    sysmsg(result);log(tool+': '+result);
    speak(result);
  }catch(e){sysmsg('error: '+e.message)}
}

function toggleMic(){
  if(!SR){var inp=document.getElementById('minput');if(inp){inp.focus();inp.placeholder='Scrivi qui...'}return}
  if(micActive){stopMic();return}
  recognition=new SR();recognition.lang='it-IT';recognition.continuous=false;
  recognition.onstart=function(){
    micActive=true;if(micbtn){micbtn.classList.add('listening');micbtn.textContent='⏹'}
    log('mic active');
  };
  recognition.onresult=function(e){
    var t='';for(var i=0;i<e.results.length;i++)t+=e.results[i][0].transcript;
    if(minput)minput.value=t;
    if(e.results[e.results.length-1].isFinal){stopMic();setTimeout(function(){doChat(t)},150)}
  };
  recognition.onerror=function(e){log('mic: '+e.error);stopMic()};
  recognition.onend=function(){if(micActive)stopMic()};
  try{recognition.start()}catch(e){log('mic: '+e.message);stopMic()}
}

function stopMic(){
  micActive=false;if(recognition)try{recognition.stop()}catch(e){}
  if(micbtn){micbtn.classList.remove('listening');micbtn.textContent='🎤'}
  log('mic stopped');
}

function resetChat(){fetch(SRV+'/api/reset',{method:'POST'}).catch(function(){});if(msgsEl)msgsEl.innerHTML='';msgCount=0;if(msgCountEl)msgCountEl.textContent='0 MSG';sysmsg('chat reset')}

function esc(t){return(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

// ══════════════════════════════════════════════════
// ── FEATURE: TIER BADGE (fast / deep model) ──
// ══════════════════════════════════════════════════
var tierHideTimer=null;
function showTierBadge(isFast,modelName){
  var el=document.getElementById('tier-indicator');
  if(!el)return;
  if(tierHideTimer){clearTimeout(tierHideTimer);}
  el.className=isFast?'fast':'deep';
  el.textContent=isFast?'⚡ FAST — '+modelName:'🧠 DEEP — '+modelName;
  tierHideTimer=setTimeout(function(){if(el)el.className='';},4000);
}

// ══════════════════════════════════════════════════
// ── FEATURE: TOOL BADGE in botmsg ──
// ══════════════════════════════════════════════════
var TOOL_ICONS={
  'calendar':'📅','mail':'📧','email':'📧','email':'📧','search':'🔍',
  'screenshot':'📸','ocr':'👁','rag':'📚','git':'🔀','browser':'🌐',
  'computer':'🖱','mouse':'🖱','keyboard':'⌨','app':'🚀','note':'📝',
  'memory':'🧠','plan':'📋','system':'⚙','weather':'🌤','webcam':'📹',
  'spotify':'🎵','music':'🎵','reminder':'⏰','file':'📄','shell':'💻',
};
function toolIcon(action){
  var l=action.toLowerCase();
  for(var k in TOOL_ICONS){if(l.includes(k))return TOOL_ICONS[k];}
  return '⚙';
}
// Aggiorna botmsg per mostrare badge styled per ogni action
var _origBotmsg=window.botmsg||null;
function botmsg(t,actions){
  if(!msgsEl)return;
  var th=document.getElementById('thinkEl');if(th)th.classList.remove('active');
  var d=document.createElement('div');d.className='msg';
  var actHtml='', imgHtml='', wc='';
  (actions||[]).forEach(function(a){
    if(a.startsWith('WEATHER_CARD:')){
      try{wc=weatherCardHTML(JSON.parse(a.slice(13)))}catch(e){}
    } else if(a.startsWith('WEBCAM:')){
      try{var wd=JSON.parse(a.slice(7));openWebcam(wd.city,wd.lat,wd.lon,wd.video_id)}catch(e){}
    } else if(a.startsWith('WEBCAM_GRID:')){
      try{var wgd=JSON.parse(a.slice(12));openWebcamGrid(wgd)}catch(e){}
    } else if(a.startsWith('WORLD_NEWS_GLOBE:')){
      window.location.hash = '#worldnews';
      setTimeout(function(){
        if(typeof wnStartAutoNews === 'function') wnStartAutoNews();
        var btn = document.getElementById('wn-autonews-btn');
        if(btn){btn.textContent='🤖 Auto News: ● ON';btn.style.borderColor='#00f0ff';btn.style.color='#00f0ff'}
      }, 3000);
    } else if(a.startsWith('IMAGE:')){
      var url=a.slice(6).trim();
      // Aggiungi timestamp per bust cache
      var src=(url.includes('?')?url:url)+'&t='+Date.now();
      imgHtml+='<div class="chat-img-wrap">'
        +'<img class="chat-img" src="'+SRV+src+'" loading="lazy" '
        +'onclick="openImgFull(this.src)" title="Clicca per ingrandire">'
        +'<a class="chat-img-dl" href="'+SRV+src+'" download target="_blank">⬇</a>'
        +'</div>';
    } else if(!a.startsWith('SPEECH:') && !a.startsWith('HA_DASHBOARD:')){
      var icon=toolIcon(a);
      var label=a.length>60?a.slice(0,60)+'…':a;
      actHtml+='<span class="tool-badge action">'+icon+' '+esc(label)+'</span>';
    }
  });
  var rendered=typeof marked!=='undefined'?marked.parse(t||''):t.replace(/\n/g,'<br>');
  d.innerHTML=
    '<div class="msg-header"><div class="msg-avatar jarvis">AI</div>'
    +'<span class="msg-name jarvis">J.A.R.V.I.S</span>'
    +'<span class="msg-time">'+ts()+'</span></div>'
    +(actHtml?'<div style="padding:4px 18px 2px;display:flex;flex-wrap:wrap;gap:2px">'+actHtml+'</div>':'')
    +wc
    +(imgHtml?'<div class="chat-imgs">'+imgHtml+'</div>':'')
    +'<div class="msg-body jarvis-msg">'+rendered+'</div>';
  msgsEl.appendChild(d);msgsEl.scrollTop=msgsEl.scrollHeight;
  msgCount++;if(msgCountEl)msgCountEl.textContent=msgCount+' MSG';
}

// Lightbox immagine a schermo intero
function openImgFull(src){
  var ov=document.getElementById('img-lightbox');
  if(!ov){
    ov=document.createElement('div');ov.id='img-lightbox';
    ov.style.cssText='position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.92);display:flex;align-items:center;justify-content:center;cursor:zoom-out;backdrop-filter:blur(4px)';
    ov.onclick=function(){ov.remove()};
    document.body.appendChild(ov);
  }
  ov.innerHTML='<img src="'+src+'" style="max-width:90vw;max-height:90vh;border-radius:6px;box-shadow:0 0 60px rgba(0,240,255,0.3);object-fit:contain">'
    +'<button style="position:absolute;top:18px;right:24px;background:none;border:none;color:#fff;font-size:28px;cursor:pointer;opacity:0.7" onclick="document.getElementById(\'img-lightbox\').remove()">✕</button>';
  ov.style.display='flex';
}

// ══════════════════════════════════════════════════
// ── FEATURE: MEMORY PANEL (view / edit / delete / add) ──
// ══════════════════════════════════════════════════
var memCache=[];
function openMem(){
  document.getElementById('mem-panel').classList.add('open');
  loadMem();
}
function closeMem(){
  document.getElementById('mem-panel').classList.remove('open');
}
function loadMem(){
  fetch(SRV+'/api/memory/all').then(function(r){return r.json()}).then(function(d){
    memCache=d.memories||[];
    renderMem(memCache);
  }).catch(function(e){log('mem load: '+e.message)});
}
function renderMem(list){
  var el=document.getElementById('mem-list');
  var lbl=document.getElementById('mem-count-label');
  if(lbl)lbl.textContent=list.length+' facts';
  if(!list||!list.length){el.innerHTML='<div id="mem-empty">NESSUN RICORDO SALVATO</div>';return;}
  el.innerHTML=list.map(function(m){
    var cat=m.category||'fact';
    var dt=m.created_at?(m.created_at.replace('T',' ').slice(0,16)):'';
    return '<div class="mem-item" data-id="'+m.id+'">'
      +'<div class="mem-item-body">'
      +'<div class="mem-item-cat">'+esc(cat)+'</div>'
      +'<div class="mem-item-text" data-orig="'+esc(m.content)+'" onclick="editMem(this)">'+esc(m.content)+'</div>'
      +'<button class="mem-save-btn" id="msave-'+m.id+'" onclick="saveMem('+m.id+',this)">SALVA</button>'
      +'<div class="mem-item-date">'+dt+'</div>'
      +'</div>'
      +'<button class="mem-del" onclick="delMem('+m.id+',this)" title="Elimina">✕</button>'
      +'</div>';
  }).join('');
}
function filterMem(q){
  if(!q){renderMem(memCache);return;}
  var low=q.toLowerCase();
  renderMem(memCache.filter(function(m){return m.content.toLowerCase().includes(low)||(m.category||'').toLowerCase().includes(low);}));
}
function editMem(el){
  el.contentEditable='true';el.focus();
  var id=el.closest('.mem-item').dataset.id;
  var btn=document.getElementById('msave-'+id);
  if(btn)btn.classList.add('visible');
  // deselect on blur
  el.onblur=function(){
    if(el.textContent.trim()===(el.dataset.orig||'')){
      el.contentEditable='false';if(btn)btn.classList.remove('visible');
    }
  };
}
function saveMem(id,btn){
  var el=btn.closest('.mem-item').querySelector('.mem-item-text');
  var newText=el.textContent.trim();
  if(!newText)return;
  fetch(SRV+'/api/memory/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,content:newText})})
    .then(function(){el.contentEditable='false';btn.classList.remove('visible');el.dataset.orig=newText;loadMem();})
    .catch(function(e){log('mem save: '+e.message)});
}
function delMem(id,btn){
  var item=btn.closest('.mem-item');
  item.style.opacity='0.4';
  fetch(SRV+'/api/memory/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id})})
    .then(function(){item.remove();memCache=memCache.filter(function(m){return m.id!==id;});
      var lbl=document.getElementById('mem-count-label');if(lbl)lbl.textContent=memCache.length+' facts';})
    .catch(function(e){item.style.opacity='1';log('mem del: '+e.message)});
}
function addMem(){
  var inp=document.getElementById('mem-add-input');
  var txt=(inp?inp.value:''||'').trim();
  if(!txt)return;
  fetch(SRV+'/api/memory/remember',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:txt,category:'user'})})
    .then(function(){if(inp)inp.value='';loadMem();})
    .catch(function(e){log('mem add: '+e.message)});
}

// ══════════════════════════════════════════════════
// ── FEATURE: RAG PANEL ──
// ══════════════════════════════════════════════════
var ragCache=[];
function toggleRag(){
  var p=document.getElementById('rag-panel');
  var open=p.classList.contains('open');
  if(open){closeRag()}else{openRag()}
}
function openRag(){
  document.getElementById('rag-panel').classList.add('open');
  loadRag();
}
function closeRag(){
  document.getElementById('rag-panel').classList.remove('open');
}
// ── Progress bar helpers ──
function showRagProgress(show){
  var w=document.getElementById('rag-progress-wrap');
  var fill=document.getElementById('rag-progress-fill');
  if(w)w.style.display=show?'block':'none';
  if(fill){
    if(show&&fill.style.width==='0%')fill.classList.add('active');
    else fill.classList.remove('active');
  }
}
function updateRagProgress(pct,label){
  var fill=document.getElementById('rag-progress-fill');
  var lbl=document.getElementById('rag-progress-label');
  if(fill){
    fill.style.width=Math.min(pct,100)+'%';
    if(pct>=100)fill.classList.remove('active');
    else if(pct>0)fill.classList.add('active');
  }
  if(lbl)lbl.textContent=label||'';
}
function loadRag(){
  fetch(SRV+'/api/rag/stats').then(function(r){return r.json()}).then(function(s){
    document.getElementById('rag-count-label').textContent=s.documents+' docs / '+s.chunks+' chunk';
    var st=document.getElementById('rag-stats');
    if(st)st.innerHTML='📄 '+s.documents+' documents &bull; 🧩 '+s.chunks+' chunks &bull; 🤖 modello: '+esc(s.model||'hash');
  }).catch(function(e){log('rag stats: '+e.message)});
  fetch(SRV+'/api/rag/list').then(function(r){return r.json()}).then(function(d){
    ragCache=d.documents||[];
    renderRag(ragCache);
  }).catch(function(e){log('rag list: '+e.message)});
}
function renderRag(list){
  var el=document.getElementById('rag-list');
  var lbl=document.getElementById('rag-count-label');
  if(!list||!list.length){el.innerHTML='<div style="padding:20px;text-align:center;color:var(--tx3);font-family:var(--fm);font-size:10px">NESSUN DOCUMENTO INDICIZZATO<br><span style="font-size:8px">usa + FILE o + CARTELLA o 📂 INDICIZZA</span></div>';return;}
  el.innerHTML=list.map(function(d){
    var dt=d.created_at?(d.created_at.replace('T',' ').slice(0,16)):'';
    var meta=d.metadata?JSON.parse(d.metadata||'{}'):{};
    var type=meta.type||'?';
    return '<div class="rag-item" data-id="'+d.id+'">'
      +'<span class="rag-title">'+esc(d.title)+'</span>'
      +'<button class="rag-del" onclick="delRag('+d.id+',this)" title="Elimina documento">✕</button>'
      +'<br><span class="rag-source">'+esc(d.source||'')+'</span>'
      +' <span class="rag-chunks">'+d.chunks+' chunk &bull; '+type+'</span>'
      +' <span class="rag-score">'+dt+'</span>'
      +'</div>';
  }).join('');
}
function filterRag(q){
  if(!q){renderRag(ragCache);return;}
  var low=q.toLowerCase();
  renderRag(ragCache.filter(function(d){return (d.title||'').toLowerCase().includes(low)||(d.source||'').toLowerCase().includes(low);}));
}
function addRagFile(){
  var inp=document.getElementById('rag-add-file');
  var path=(inp?inp.value:'').trim();
  if(!path){sysmsg('⚠ RAG: inserisci un percorso file valido');return;}
  fetch(SRV+'/api/rag/add_file',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({file_path:path})})
    .then(function(r){return r.json()}).then(function(d){
      if(inp)inp.value='';
      if(d.result&&d.result.status==='ok'){
        sysmsg('✅ RAG: aggiunto '+d.result.title+' ('+d.result.chunks+' chunk)');
      }else{
        sysmsg('⚠ RAG: '+(d.result&&d.result.message||(d.error||'errore sconosciuto')));
      }
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG errore: '+e.message)});
}
function addRagFolderStream(){
  var inp=document.getElementById('rag-add-file');
  var path=(inp?inp.value:'').trim();
  if(!path){sysmsg('⚠ RAG: inserisci un percorso cartella valido');return;}
  if(inp)inp.value='';
  var pw=document.getElementById('rag-progress-wrap');
  console.log('[RAG] addRagFolderStream called, progress-wrap:',pw);
  showRagProgress(true);
  updateRagProgress(0,'Indicizzazione in corso... 0%');
  sysmsg('📂 RAG: indicizzazione '+path+' ...');
  fetch(SRV+'/api/rag/add_folder',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({folder_path:path,recursive:true})})
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){sysmsg('⚠ RAG cartella: '+d.error);loadRag();showRagProgress(false);return;}
      var r=d.result||{};
      if(r.status==='error'){
        sysmsg('⚠ RAG cartella: '+(r.message||'errore sconosciuto'));
      }else if(r.status==='ok'){
        updateRagProgress(100,'✅ '+r.indexed+'/'+r.total+' file indicizzati');
        setTimeout(function(){showRagProgress(false)},1500);
        sysmsg('📂 RAG: indicizzati '+(r.indexed||0)+'/'+(r.total||0)+' file'+(r.skipped?' ('+r.skipped+' già presenti)':''));
      }else{
        sysmsg('⚠ RAG cartella: risposta sconosciuta');
        showRagProgress(false);
      }
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG errore: '+e.message);showRagProgress(false)});
}
function addRagFolder(){
  var inp=document.getElementById('rag-add-file');
  var path=(inp?inp.value:'').trim();
  if(!path){sysmsg('⚠ RAG: inserisci un percorso cartella valido');return;}
  fetch(SRV+'/api/rag/add_folder',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({folder_path:path,recursive:true})})
    .then(function(r){return r.json()}).then(function(d){
      if(inp)inp.value='';
      if(d.error){sysmsg('⚠ RAG cartella: '+d.error);loadRag();return;}
      var r=d.result||{};
      if(r.status==='error'){
        sysmsg('⚠ RAG cartella: '+(r.message||'errore sconosciuto'));
      }else if(r.status==='ok'){
        sysmsg('📂 RAG: indicizzati '+(r.indexed||0)+'/'+(r.total||0)+' file'+(r.skipped?' ('+r.skipped+' già presenti)':''));
      }else{
        sysmsg('⚠ RAG cartella: risposta sconosciuta');
      }
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG errore: '+e.message)});
}
function ingestRag(){
  sysmsg('📂 RAG: indicizzazione data/documents/ e data/...');
  fetch(SRV+'/api/rag/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){sysmsg('⚠ RAG ingest: '+d.error);loadRag();return;}
      var results=d.results||[];
      var total=results.reduce(function(a,r){return a+(r.indexed||0)},0);
      var skipped=results.reduce(function(a,r){return a+(r.skipped||0)},0);
      var msg='✅ RAG: indicizzati '+total+' file da '+results.length+' cartelle';
      if(skipped)msg+=' ('+skipped+' già presenti)';
      sysmsg(msg);
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG ingest errore: '+e.message)});
}
function delRag(id,btn){
  var item=btn.closest('.rag-item');
  if(item)item.style.opacity='0.3';
  fetch(SRV+'/api/rag/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({doc_id:id})})
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){sysmsg('⚠ RAG elimina: '+d.error)}
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG elimina errore: '+e.message);if(item)item.style.opacity='1'});
}
function clearRag(){
  if(!confirm('🗑 ELIMINARE TUTTI i documenti dal database RAG?'))return;
  fetch(SRV+'/api/rag/delete_all',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){sysmsg('⚠ RAG svuota: '+d.error);return;}
      sysmsg('🗑 RAG: database svuotato');
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG svuota errore: '+e.message)});
}
function reembedRag(){
  if(!confirm('🔄 RIGENERARE TUTTI gli embedding? (utile dopo cambio modello)'))return;
  showRagProgress(true);
  updateRagProgress(0,'Re-embedding chunk...');
  sysmsg('🔄 RAG: rigenerazione embedding...');
  fetch(SRV+'/api/rag/reembed',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){
      var reader=r.body.getReader();
      var decoder=new TextDecoder();
      var buffer='';
      function readChunk(){
        reader.read().then(function(d){
          if(d.done){showRagProgress(false);loadRag();return;}
          buffer+=decoder.decode(d.value,{stream:true});
          var lines=buffer.split('\n');
          buffer=lines.pop()||'';
          lines.forEach(function(line){
            if(line.startsWith('data: ')){
              try{
                var ev=JSON.parse(line.slice(6));
                if(ev.type==='progress'){
                  updateRagProgress(ev.percent,'Re-embedding: '+ev.label);
                }else if(ev.type==='complete'){
                  var r2=ev.result||{};
                  sysmsg('🔄 RAG: re-embedded '+(r2.reembedded||0)+' chunk');
                  showRagProgress(false);
                  loadRag();
                }
              }catch(e){}
            }
          });
          readChunk();
        }).catch(function(e){
          showRagProgress(false);
          sysmsg('⚠ RAG reembed: '+e.message);
        });
      }
      readChunk();
    }).catch(function(e){
      showRagProgress(false);
      sysmsg('⚠ RAG reembed: '+e.message);
    });
}
function exportRag(){
  sysmsg('💾 RAG: esportazione database...');
  fetch(SRV+'/api/rag/export',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json()}).then(function(d){
      var blob=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});
      var a=document.createElement('a');
      a.href=URL.createObjectURL(blob);
      a.download='rag_export_'+new Date().toISOString().slice(0,10)+'.json';
      a.click();
      sysmsg('💾 RAG: esportati '+(d.documents?d.documents.length:0)+' documenti');
    }).catch(function(e){sysmsg('⚠ RAG export: '+e.message)});
}
function dedupRag(){
  if(!confirm('🧹 AVVIARE DEDUPLICAZIONE? (rimuove documenti con contenuto identico o quasi)'))return;
  sysmsg('🧹 RAG: deduplicazione in corso...');
  fetch(SRV+'/api/rag/dedup',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({threshold:0.95})})
    .then(function(r){return r.json()}).then(function(d){
      var r=d.result||{};
      sysmsg('🧹 RAG: rimossi '+(r.removed||0)+' duplicati');
      loadRag();
    }).catch(function(e){sysmsg('⚠ RAG dedup: '+e.message)});
}

// ══════════════════════════════════════════════════
// ── FEATURE: WORLD NEWS PANEL v10.0 ──
// ══════════════════════════════════════════════════
function openWorldNews(){
  try {
    var p=document.getElementById('worldnews-panel');
    if(!p){console.error('WN: no panel');return}
    p.style.display='flex';
    p.classList.add('open');
    var retries=0;
    function tryInit(){
      if(typeof wnInit==='function'){wnInit();return}
      retries++;
      if(retries<100) setTimeout(tryInit, 200);
      else console.error('WN: wnInit not defined after 100 retries');
    }
    setTimeout(tryInit, 100);
  } catch(e){console.error('WN open error:',e)}
}
function closeWorldNews(){
  var p=document.getElementById('worldnews-panel');
  if(p){
    p.style.transition='opacity .3s ease,transform .3s ease';
    p.style.opacity='0';
    p.style.transform='scale(0.95)';
    setTimeout(function(){
      p.style.display='none';
      p.classList.remove('open');
      p.style.opacity='1';
      p.style.transform='scale(1)';
    }, 300);
  }
}
window.closeWorldNews = closeWorldNews;

// ══════════════════════════════════════════════════
// ── FEATURE: TRENDS PANEL v9.3 ──
// ══════════════════════════════════════════════════
var trendsCat='technology';
function openTrends(){
  document.getElementById('trends-panel').classList.add('open');
}
function closeTrends(){
  document.getElementById('trends-panel').classList.remove('open');
}
function trendsSetCat(btn){
  document.querySelectorAll('.trends-cat').forEach(function(c){c.classList.remove('active')});
  btn.classList.add('active');
  trendsCat=btn.dataset.cat;
  trendsRefresh();
}
function trendsSearch(){
  var inp=document.getElementById('trends-search-input');
  var q=inp?inp.value.trim():'';
  if(!q){trendsRefresh();return;}
  var region=document.getElementById('trends-region').value||'wt';
  var st=document.getElementById('trends-status');
  if(st)st.textContent='🔍 Cerco: '+q+'...';
  fetch(SRV+'/api/trends/search',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({query:q,region:region,max_results:15})})
    .then(function(r){return r.json()}).then(function(d){
      renderTrends(d);
      if(st)st.textContent='✅ '+d.count+' risultati per "'+q+'"';
    }).catch(function(e){sysmsg('⚠ Trends: '+e.message);if(st)st.textContent='⚠ Errore'});
}
function trendsRefresh(){
  var region=document.getElementById('trends-region').value||'it';
  var st=document.getElementById('trends-status');
  if(st)st.textContent='🔄 Caricamento trend '+trendsCat+'...';
  fetch(SRV+'/api/trends?category='+trendsCat+'&region='+region)
    .then(function(r){return r.json()}).then(function(d){
      renderTrends(d);
      if(st)st.textContent='✅ '+d.count+' trend — '+trendsCat.toUpperCase()+' ('+region+')';
    }).catch(function(e){sysmsg('⚠ Trends: '+e.message);if(st)st.textContent='⚠ Errore'});
}
function renderTrends(data){
  var el=document.getElementById('trends-list');
  var lbl=document.getElementById('trends-count-label');
  if(!data||!data.results||!data.results.length){
    el.innerHTML='<div style="padding:40px;text-align:center;color:var(--tx3);font-family:var(--fm);font-size:10px">NESSUN RISULTATO</div>';
    if(lbl)lbl.textContent='0 results';
    return;
  }
  if(lbl)lbl.textContent=data.count+' results';
  el.innerHTML=data.results.map(function(r,i){
    var snippet=(r.snippet||'').slice(0,150);
    var icon=['💻','🤖','📱','🚀','🔓','🇩🇪','🇮🇹'][i%7];
    return '<div class="trends-item" style="padding:6px 8px;margin:3px 0;background:var(--n2);border:1px solid var(--n3);border-radius:3px">'
      +'<div style="display:flex;justify-content:space-between;align-items:center">'
      +'<a href="'+esc(r.url||'')+'" target="_blank" style="color:var(--cy);text-decoration:none;font-size:10px;font-family:var(--fm);font-weight:600;flex:1">'
      +icon+' '+esc(r.title||'')+'</a>'
      +'<button onclick="trendsCopyLink(this)" data-url="'+esc(r.url||'')+'" style="background:none;border:1px solid var(--n3);color:var(--tx3);padding:2px 6px;font-size:8px;cursor:pointer;border-radius:2px">COPY</button>'
      +'</div>'
      +'<div style="font-size:8px;color:var(--tx3);margin-top:2px">'+esc(snippet)+'</div>'
      +'</div>';
  }).join('');
}
function trendsCopyLink(btn){
  var url=btn.dataset.url;
  if(!url)return;
  var ta=document.createElement('textarea');
  ta.value=url;document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);
  sysmsg('📋 Link copiato: '+url.slice(0,50)+'...');
}
function sendTelegram(){
  var inp=document.getElementById('trends-search-input');
  var msg=inp?inp.value.trim():'';
  if(!msg){sysmsg('⚠ Inserisci un messaggio');return;}
  fetch(SRV+'/api/telegram/send',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:msg})})
    .then(function(r){return r.json()}).then(function(d){
      sysmsg(d.result||'✅ Telegram inviato');
      if(inp)inp.value='';
    }).catch(function(e){sysmsg('⚠ Telegram: '+e.message)});
}

// ── INIT ──
var holoState='idle';
window.addEventListener('DOMContentLoaded',function(){
  loadTheme();
  msgsEl=document.getElementById('msgs');spkbar=document.getElementById('spkbar');
  sendbtn=document.getElementById('sendbtn');micbtn=document.getElementById('micbtn');
  minput=document.getElementById('minput');msgCountEl=document.getElementById('msg-count');
  logBox=document.getElementById('log-box');

  minput.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});

  setTimeout(function(){sysmsg('J.A.R.V.I.S v9.1 // CYBERPUNK HUD')},200);
  setTimeout(ping,800);
  if(!SR&&micbtn&&window.innerWidth>480)micbtn.style.opacity='0.3';
  document.getElementById('wake-indicator').addEventListener('click',toggleWake);
  setInterval(ping,30000);setInterval(pollWakeStatus,10000);setInterval(tick,1000);setInterval(loadSysInfo,20000);
  tick();loadWeather();setInterval(loadWeather,300000);loadSysInfo();
  initHoloCanvas();
  initWidgetCanvas();
});

// ── escHtml alias (used by pages loaded via innerHTML) ──
function escHtml(s){return esc(s)}

// ── GIT ──
var gitView = 'status';
async function openGit(){
  document.getElementById('git-panel').classList.add('open');
  await gitStatus();
}
function closeGit(){
  document.getElementById('git-panel').classList.remove('open');
}
async function gitCall(tool, args){
  var r = await fetch('/api/tool', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({tool:tool, args:args||{}})});
  return (await r.json()).result || '';
}
function gitRender(text){
  var el = document.getElementById('git-content');
  el.innerHTML = '<pre style="margin:0;white-space:pre-wrap;word-break:break-all;font-family:var(--fm);color:var(--tx2);font-size:9px">'+escHtml(text)+'</pre>';
}
async function gitStatus(){
  gitView = 'status';
  var el = document.getElementById('git-content');
  el.innerHTML = '<div style="padding:12px;color:var(--tx3);font-size:9px">⏳ git status...</div>';
  try {
    var s = await gitCall('git_status');
    var br = '';
    if(s && s.includes('On branch')) br = s.match(/On branch\s+(\S+)/)?.[1]||'';
    document.getElementById('git-branch-label').textContent = br ? '⎇ '+br : '';
    gitRender(s);
  } catch(e){ gitRender('Errore: '+e.message); }
}
async function gitLog(){
  gitView = 'log';
  var el = document.getElementById('git-content');
  el.innerHTML = '<div style="padding:12px;color:var(--tx3);font-size:9px">⏳ git log...</div>';
  try {
    var s = await gitCall('git_log', {limit:30});
    gitRender(s);
  } catch(e){ gitRender('Errore: '+e.message); }
}
async function gitBranches(){
  gitView = 'branches';
  var el = document.getElementById('git-content');
  el.innerHTML = '<div style="padding:12px;color:var(--tx3);font-size:9px">⏳ git branches...</div>';
  try {
    var s = await gitCall('git_branches');
    gitRender(s);
  } catch(e){ gitRender('Errore: '+e.message); }
}
async function gitDiff(){
  gitView = 'diff';
  var el = document.getElementById('git-content');
  el.innerHTML = '<div style="padding:12px;color:var(--tx3);font-size:9px">⏳ git diff...</div>';
  try {
    var s = await gitCall('git_diff');
    gitRender(s || '(nessuna modifica)');
  } catch(e){ gitRender('Errore: '+e.message); }
}
async function gitCommit(){
  var msg = prompt('Messaggio commit:');
  if(!msg) return;
  var el = document.getElementById('git-content');
  el.innerHTML = '<div style="padding:12px;color:var(--cy);font-size:9px">⏳ git commit...</div>';
  try {
    var r = await fetch('/api/git/commit', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg})});
    var d = await r.json();
    el.innerHTML = '<pre style="margin:0;color:#0f0;font-size:9px">'+(d.status||d.result||JSON.stringify(d))+'</pre>';
  } catch(e){
    el.innerHTML = '<pre style="margin:0;color:#f44;font-size:9px">Errore: '+e.message+'</pre>';
  }
}

// ── GOALS ──
async function openGoals(){
  document.getElementById('goals-panel').classList.add('open');
  await goalsRefresh();
}
function closeGoals(){
  document.getElementById('goals-panel').classList.remove('open');
}
async function goalsRefresh(){
  var el = document.getElementById('goals-content');
  el.innerHTML = '<div style="padding:12px;text-align:center;color:var(--tx3);font-size:9px">⏳ caricamento...</div>';
  try {
    var r = await fetch('/api/goals');
    var d = await r.json();
    var goals = d.goals || [];
    document.getElementById('goals-count').textContent = goals.length+' GOALS';
    el.innerHTML = '';
    if(goals.length === 0){
      el.innerHTML = '<div style="padding:30px;text-align:center;color:var(--tx3);font-size:10px">Nessun goal. Creane uno sopra!</div>';
      return;
    }
    goals.forEach(function(g){
      var title = g.title||'Goal';
      var desc = g.description||'';
      var krs = Array.isArray(g.key_results) ? g.key_results : [];
      var done = krs.filter(function(k){return k.current >= k.target}).length;
      var pct = g.progress || (krs.length > 0 ? Math.round(done/krs.length*100) : 0);
      var card = document.createElement('div');
      card.className = 'goal-card';
      var krHtml = krs.map(function(kr){
        var t = kr.description||'KR';
        var crossed = kr.current >= kr.target;
        return '<div class="goal-kr-item'+(crossed?' crossed':'')+'">'+
          '<input type="checkbox"'+(crossed?' checked':'')+' onchange="goalsToggleKR('+g.id+','+kr.id+',this.checked)">'+
          '<span>'+(crossed?'✅ ':'⬜ ')+escHtml(t)+' ('+kr.current+'/'+kr.target+kr.unit+')</span></div>';
      }).join('');
      card.innerHTML = '<h4>'+escHtml(title)+' <span style="font-size:9px;color:var(--tx3)">'+pct+'%</span></h4>'+
        (desc ? '<div class="gdesc">'+escHtml(desc)+'</div>' : '')+
        '<div class="goal-progress"><div class="goal-progress-fill" style="width:'+pct+'%"></div></div>'+
        '<div style="font-size:8px;color:var(--tx3);margin-bottom:4px">'+done+'/'+krs.length+' KR</div>'+
        krHtml+
        '<div class="goal-actions">'+
        '<button onclick="goalsAddKR('+g.id+')">+ KR</button>'+
        '<button onclick="goalsDelete('+g.id+')" style="color:#f44">🗑</button>'+
        '</div>';
      el.appendChild(card);
    });
  } catch(e){
    el.innerHTML = '<div style="padding:12px;color:#f44;font-size:10px">Errore: '+e.message+'</div>';
  }
}
async function goalsCreate(){
  var title = document.getElementById('goals-title-input').value.trim();
  var desc = document.getElementById('goals-desc-input').value.trim();
  if(!title) return;
  await fetch('/api/goals/create', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({title:title, description:desc})});
  document.getElementById('goals-title-input').value = '';
  document.getElementById('goals-desc-input').value = '';
  goalsRefresh();
}
async function goalsAddKR(goalId){
  var title = prompt('KR title:');
  if(!title) return;
  await fetch('/api/goals/add_kr', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({goal_id:goalId, title:title, target:100})});
  goalsRefresh();
}
async function goalsToggleKR(goalId, krId, checked){
  await fetch('/api/goals/update_kr', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({goal_id:goalId, kr_id:krId, current:checked?100:0})});
  goalsRefresh();
}
async function goalsDelete(goalId){
  if(!confirm('Eliminare questo goal?')) return;
  await fetch('/api/goals/delete', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:goalId})});
  goalsRefresh();
}

// ── VISION ──
var visionTimer = null;
var visionFrameTimer = null;
var visionMjpegImg = null;
async function openVision(){
  closeVision();
  document.getElementById('vision-panel').classList.add('open');
  await visionRefresh();
}
function closeVision(){
  document.getElementById('vision-panel').classList.remove('open');
  if(visionTimer){ clearInterval(visionTimer); visionTimer = null; }
  if(visionFrameTimer){ clearInterval(visionFrameTimer); visionFrameTimer = null; }
  stopVisionMjpeg();
}
async function visionRefresh(){
  var el = document.getElementById('vision-content');
  if(!el) return;
  // Fetch status
  try {
    var rs = await fetch('/api/video/analytics/status');
    var st = await rs.json();
    var rc = await fetch('/api/video/analytics/counts?hours='+encodeURIComponent(document.getElementById('vision-hours')?.value||24));
    var ct = await rc.json();
    visionUpdateUI(st, ct);
  } catch(e){
    var ste = document.getElementById('vision-status-text');
    if(ste) ste.innerHTML = '<span style="color:#f44">Errore: '+e.message+'</span>';
  }
}
function visionUpdateUI(st, ct){
  var ste = document.getElementById('vision-status-text');
  if(ste){
    var modelIcon = st.model && st.model.includes('YOLO') ? '🧠' : '⚙';
    var runIcon = st.running ? '🟢' : '🔴';
    ste.innerHTML = runIcon+' <b>Stato:</b> '+(st.running?'Attivo':'Fermo')+
      ' | '+modelIcon+' <b>Modello:</b> '+(st.model||'—')+
      ' | 📡 <b>FPS:</b> '+(st.fps||0).toFixed(1)+
      ' | 🖼 <b>Frame:</b> '+(st.frames_processed||0)+
      ' | 🎯 <b>Linea:</b> '+(st.detection_line ? Math.round(st.detection_line*100)+'%' : '—')+
      ' | ⚡ <b>Vel:</b> '+(st.latest_speed_kmh||0)+' km/h';
  }
  var startBtn = document.getElementById('vision-start-btn');
  var stopBtn = document.getElementById('vision-stop-btn');
  var offline = document.getElementById('vision-stream-offline');
    if(st.running){
    if(startBtn) startBtn.style.display = 'none';
    if(stopBtn) stopBtn.style.display = 'inline-block';
    if(!visionTimer) visionTimer = setInterval(visionRefresh, 2000);
    if(offline) offline.style.display = 'none';
    startVisionMjpeg();
  } else {
    if(startBtn) startBtn.style.display = 'inline-block';
    if(stopBtn) stopBtn.style.display = 'none';
    if(visionTimer){ clearInterval(visionTimer); visionTimer = null; }
    stopVisionMjpeg();
    if(visionFrameTimer){ clearInterval(visionFrameTimer); visionFrameTimer = null; }
    if(offline) offline.style.display = 'block';
  }
  if(ct){
    var sessionCars = st && st.car_count_session != null ? st.car_count_session : (ct.cars||0);
    var sessionPeople = st && st.people_count_session != null ? st.people_count_session : (ct.people||0);
    var sessionTrucks = st && st.truck_count_session != null ? st.truck_count_session : 0;
    var sessionBuses = st && st.bus_count_session != null ? st.bus_count_session : 0;
    var sessionMotos = st && st.moto_count_session != null ? st.moto_count_session : 0;
    var vc = document.getElementById('vision-cars');
    if(vc) vc.textContent = sessionCars;
    var vt = document.getElementById('vision-trucks');
    if(vt) vt.textContent = sessionTrucks;
    var vbm = document.getElementById('vision-busmoto');
    if(vbm) vbm.textContent = sessionBuses + sessionMotos;
    var vp = document.getElementById('vision-people');
    if(vp) vp.textContent = sessionPeople;
    var spd = document.getElementById('vision-speed');
    var liveSpd = st && st.latest_speed_kmh ? st.latest_speed_kmh : (ct.avg_speed_kmh||0);
    if(spd) spd.textContent = liveSpd+' km/h';
    var badge = document.getElementById('vision-status-badge');
    if(badge) badge.textContent = sessionCars+'🚗 '+sessionTrucks+'🚛 '+sessionPeople+'👤';
    var hist = document.getElementById('vision-historical-text');
    if(hist){
      var since = ct.since ? new Date(ct.since+'Z').toLocaleString() : '—';
      var liveInfo = st && st.latest_speed_kmh ? '⚡ <b>Ora:</b> '+st.latest_speed_kmh+' km/h | ' : '';
      hist.innerHTML =
        liveInfo+
        '📈 <b>Intervalli:</b> '+ct.intervals+' ore | '+
        '🚗 <b>Auto:</b> '+ct.cars+' | '+
        '🚛 <b>Camion:</b> '+sessionTrucks+' | '+
        '🧑 <b>Persone:</b> '+ct.people+' | '+
        '📊 <b>Media:</b> '+(ct.avg_speed_kmh||0)+' km/h | '+
        '⏱ <b>Dal:</b> '+since;
    }
  }
}
async function visionStart(){
  var url = document.getElementById('vision-url-input')?.value.trim();
  if(!url){ alert('Inserisci un URL RTSP valido'); return; }
  var btn = document.getElementById('vision-start-btn');
  if(btn) btn.textContent = '⏳...';
  try {
    var r = await fetch('/api/video/analytics/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({stream_url: url})});
    var d = await r.json();
    await visionRefresh();
  } catch(e){
    alert('Errore: '+e.message);
  }
  if(btn) btn.innerHTML = '▶ START';
}
async function visionStop(){
  var btn = document.getElementById('vision-stop-btn');
  if(btn) btn.textContent = '⏳...';
  try {
    await fetch('/api/video/analytics/stop', {method:'POST'});
    await visionRefresh();
  } catch(e){
    alert('Errore: '+e.message);
  }
  if(btn) btn.innerHTML = '⏹ STOP';
}
function startVisionMjpeg(){
  if(visionMjpegImg) return;
  var canvas = document.getElementById('vision-canvas');
  if(!canvas) return;
  var ctx = canvas.getContext('2d');
  visionMjpegImg = {active:true};
  var lastFrame = 0;
  (function loop(){
    if(!visionMjpegImg || !visionMjpegImg.active) return;
    var now = Date.now();
    if(now - lastFrame < 50){ setTimeout(loop, 50 - (now - lastFrame)); return; }
    lastFrame = now;
    fetch('/api/video/analytics/frame?_='+now).then(function(r){
      if(!r.ok){ setTimeout(loop, 50); return; }
      return r.blob();
    }).then(function(blob){
      if(!blob){ setTimeout(loop, 50); return; }
      var img = new Image();
      img.onload = function(){
        if(!visionMjpegImg || !visionMjpegImg.active){ URL.revokeObjectURL(img.src); return; }
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(img.src);
        setTimeout(loop, 16);
      };
      img.onerror = function(){ URL.revokeObjectURL(img.src); setTimeout(loop, 50); };
      img.src = URL.createObjectURL(blob);
    }).catch(function(){ setTimeout(loop, 100); });
  })();
}
function stopVisionMjpeg(){
  if(visionMjpegImg){ visionMjpegImg.active = false; visionMjpegImg = null; }
  if(visionFrameTimer){ clearInterval(visionFrameTimer); visionFrameTimer = null; }
}
async function visionReset(){
  if(!confirm('Azzera tutto lo storico video analytics?')) return;
  try {
    await fetch('/api/video/analytics/reset', {method:'POST'});
    await visionRefresh();
  } catch(e){ alert('Errore: '+e.message); }
}
async function visionUpdateCal(val){
  document.getElementById('vision-cal-value').textContent = val;
  try {
    await fetch('/api/video/analytics/calibrate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({value:parseFloat(val)})});
  } catch(e){}
}

// ── SETTINGS ──
async function openSettings(){
  document.getElementById('settings-panel').classList.add('open');
  await settingsRefresh();
}
function closeSettings(){
  document.getElementById('settings-panel').classList.remove('open');
}
async function settingsRefresh(){
  await settingsLoadProviders();
  await settingsLoadVoices();
  await settingsLoadInfo();
}
async function settingsLoadProviders(){
  var el = document.getElementById('settings-providers');
  try {
    var r = await fetch('/api/providers');
    var d = await r.json();
    var providersList = d.providers || [];
    var current = d.current || 'groq';
    el.innerHTML = '';
    providersList.forEach(function(name){
      var btn = document.createElement('button');
      btn.className = 'st-btn' + (name === current ? ' active' : '');
      btn.textContent = name.toUpperCase();
      btn.onclick = function(){ settingsSwitchProvider(name); };
      el.appendChild(btn);
    });
  } catch(e){ el.innerHTML = '<span style="color:var(--tx3);font-size:9px">N/D</span>'; }
}
async function settingsLoadVoices(){
  var el = document.getElementById('settings-voices');
  try {
    var r = await fetch('/api/voice/list');
    var d = await r.json();
    var voices = Array.isArray(d) ? d : (d.voices||[]);
    var current = d.current||'';
    el.innerHTML = '';
    voices.forEach(function(v){
      var name = typeof v === 'string' ? v : (v.name||v.id||'');
      var btn = document.createElement('button');
      btn.className = 'st-btn' + (name === current ? ' voice-active' : '');
      btn.textContent = name.charAt(0).toUpperCase() + name.slice(1);
      btn.onclick = function(){ settingsSetVoice(name); };
      el.appendChild(btn);
    });
  } catch(e){ el.innerHTML = '<span style="color:var(--tx3);font-size:9px">N/D</span>'; }
}
async function settingsLoadInfo(){
  var el = document.getElementById('settings-info');
  try {
    var r = await fetch('/api/status');
    var d = await r.json();
    el.innerHTML =
      '🧠 <b>Modello:</b> '+(d.model||'—')+'<br>'+
      '🎤 <b>Voce:</b> '+(d.voice||'—')+'<br>'+
      '📦 <b>Tool:</b> '+(d.tools||d.tool_count||'—')+'<br>'+
      '📚 <b>RAG docs:</b> '+(d.rag_docs||d.rag_count||'—')+'<br>'+
      '🔋 <b>Versione:</b> '+d.version+'<br>';
    if(d.uptime) el.innerHTML += '⏱ <b>Uptime:</b> '+d.uptime+'<br>';
  } catch(e){ el.innerHTML = 'Errore: '+e.message; }
}
async function settingsSwitchProvider(name){
  await fetch('/api/tool', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({tool:'providers_switch', args:{provider:name}})});
  await settingsLoadProviders();
}
async function settingsSetVoice(name){
  await fetch('/api/voice/set', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({voice:name})});
  await settingsLoadVoices();
}
