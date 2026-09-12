import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const VISEMES = ['viseme_sil','viseme_PP','viseme_FF','viseme_TH','viseme_DD','viseme_kk','viseme_CH','viseme_SS','viseme_nn','viseme_RR','viseme_aa','viseme_E','viseme_I','viseme_O','viseme_U'];
const HOLO_COLOR = new THREE.Color(0x4ad8ff);
const RIM_COLOR  = new THREE.Color(0x00f0ff);

let renderer, scene, camera, clock, mixer, idleAction;
let avatarRoot=null, faceMesh=null, teethMesh=null, headBone=null;
let morphDict=null;
let morphMeshes=[]; // every mesh that carries face/viseme morph targets
let audioCtx=null, analyser=null, freqData=null, timeData=null;
let currentSource=null, currentEndCb=null;
let state='idle';
let smoothJaw=0, smoothA=0, smoothO=0, smoothE=0;
let blinkT=0, nextBlinkAt=2+Math.random()*3;
let headSwayT=0;
let camStartTarget=null;

function showLoading(msg){
  const lo = document.getElementById('avatar3d-loading');
  if(lo){ lo.textContent = msg; }
}
function showError(msg){
  const lo = document.getElementById('avatar3d-loading');
  if(lo){ lo.textContent = msg; lo.style.color='#ff5577'; lo.style.textShadow='0 0 12px rgba(255,85,119,0.7)'; lo.style.opacity='1'; lo.style.visibility='visible'; }
  console.error('[Avatar3D]', msg);
}
window.addEventListener('error', (e)=>{ showError('ERR: '+(e.message||e.error||'unknown')) });
window.addEventListener('unhandledrejection', (e)=>{ showError('PROMISE: '+(e.reason&&e.reason.message||e.reason||'unknown')) });

let _avatarInited = false;
function initThree(){
  if (_avatarInited) return true;
  const canvas = document.getElementById('avatar3d-canvas');
  if(!canvas){
    /* La pagina chat (con il canvas) arriva via XHR dopo DOMContentLoaded: riprova */
    if (!window._avatarRetryN) window._avatarRetryN = 0;
    if (window._avatarRetryN < 40) {
      window._avatarRetryN++;
      setTimeout(initThree, 500);
    } else {
      showError('canvas non trovato');
    }
    return false;
  }
  try{
    renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true, premultipliedAlpha:false});
  }catch(e){ showError('WebGL init fail: '+e.message); return false; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  resize();

  scene = new THREE.Scene();
  scene.background = null;

  camera = new THREE.PerspectiveCamera(28, 1, 0.05, 50);
  camera.position.set(0, 1.55, 0.9);
  camera.lookAt(0, 1.55, 0);

  const amb = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(amb);
  const key = new THREE.DirectionalLight(0xffffff, 1.4);
  key.position.set(0.6, 2.2, 1.6); scene.add(key);
  const rim = new THREE.DirectionalLight(0x00f0ff, 1.1);
  rim.position.set(-1.4, 1.6, -1.0); scene.add(rim);
  const fill = new THREE.PointLight(0xff00aa, 0.45, 5);
  fill.position.set(0.9, 1.5, 0.8); scene.add(fill);

  clock = new THREE.Clock();
  showLoading('CARICANDO MODELLO 3D...');
  _avatarInited = true;
  loadAvatar();
  window.addEventListener('resize', resize);
  try{
    const ro = new ResizeObserver(()=>resize());
    ro.observe(canvas.parentElement || canvas);
  }catch(e){}
  setTimeout(resize, 100);
  setTimeout(resize, 500);
  renderer.setAnimationLoop(tick);
  return true;
}

function resize(){
  if(!renderer) return;
  const canvas = renderer.domElement;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(2, rect.width|0), h = Math.max(2, rect.height|0);
  renderer.setSize(w, h, false);
  if(camera){ camera.aspect = w/h; camera.updateProjectionMatrix(); }
}

function loadAvatar(){
  const loader = new GLTFLoader();
  const glbUrl = (window.SRV||'') + '/assets/avatar.glb?v=' + Date.now();
  showLoading('CARICANDO MODELLO 3D... 0%');
  loader.load(glbUrl, (gltf)=>{
    try{
      avatarRoot = gltf.scene;
      const meshes = [];
      morphMeshes = [];
      avatarRoot.traverse((o)=>{
        if(o.isMesh || o.isSkinnedMesh){
          meshes.push(o);
          applyHoloTint(o);
          if(o.morphTargetDictionary && o.morphTargetInfluences && o.morphTargetDictionary.jawOpen!==undefined){
            morphMeshes.push(o);
            // Prefer the head mesh as primary reference for the morph dict
            if(/head/i.test(o.name||'') || !faceMesh){ faceMesh = o; morphDict = o.morphTargetDictionary; }
            if(/teeth/i.test(o.name||'')) teethMesh = o;
          }
          o.frustumCulled = false;
        }
        if(o.isBone && /^head$|head/i.test(o.name||'') && !headBone) headBone = o;
      });

      scene.add(avatarRoot);
      avatarRoot.updateMatrixWorld(true);

      // Aim the camera at the head bone (robust for skinned half-body avatars).
      const target = new THREE.Vector3(0, 1.6, 0);
      if(headBone){
        headBone.getWorldPosition(target);
        target.y += 0.08; // head bone sits ~jaw level -> nudge up to center the face
      } else {
        const box = new THREE.Box3().setFromObject(avatarRoot);
        target.set((box.min.x+box.max.x)/2, box.max.y - (box.max.y-box.min.y)*0.08, (box.min.z+box.max.z)/2);
      }
      camStartTarget = target.clone();
      // Head-and-shoulders bust framing, camera in front (+Z) of the face.
      camera.position.set(target.x, target.y + 0.02, target.z + 0.72);
      camera.lookAt(target.x, target.y, target.z);
      camera.near = 0.01; camera.far = 50; camera.updateProjectionMatrix();

      if(gltf.animations && gltf.animations.length){
        mixer = new THREE.AnimationMixer(avatarRoot);
        const idleClip = gltf.animations.find(a=>/idle|breath/i.test(a.name||'')) || gltf.animations[0];
        idleAction = mixer.clipAction(idleClip);
        idleAction.setLoop(THREE.LoopRepeat, Infinity);
        idleAction.timeScale = 0.7;
        idleAction.play();
      }

      const cnv = document.getElementById('avatar3d-canvas');
      if(cnv) cnv.classList.add('ready');
      const wg = document.getElementById('avatar-widget');
      if(wg) wg.classList.add('has-3d');
      const lo = document.getElementById('avatar3d-loading');
      if(lo) lo.style.display='none';

      const info = `meshes=${meshes.length} face=${faceMesh?'YES':'NO'} morphs=${morphDict?Object.keys(morphDict).length:0} anims=${(gltf.animations||[]).length} headBone=${headBone?'YES':'NO'}`;
      console.log('[Avatar3D] loaded', info);
      if(!faceMesh) showError('Modello senza morph targets jawOpen');
    }catch(e){ showError('Post-load: '+e.message); console.error(e); }
  }, (p)=>{
    if(p && p.total){
      const pct = Math.round(p.loaded/p.total*100);
      showLoading('CARICANDO MODELLO 3D... '+pct+'%');
    }
  }, (err)=>{
    showError('GLB load fail: '+(err&&err.message||err));
    console.error('GLB load error', err);
  });
}

function applyHoloTint(mesh){
  const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  mats.forEach((m)=>{
    if(!m) return;
    const isFace = (mesh===faceMesh) || /avatar|head|face|skin/i.test(mesh.name||'') || (m.morphTargets);
    if('emissive' in m && m.emissive){
      m.emissive.copy(HOLO_COLOR).multiplyScalar(isFace?0.20:0.13);
    }
    if('emissiveIntensity' in m) m.emissiveIntensity = isFace?0.45:0.30;
    if(m.map) m.emissiveMap = m.map;
    if('transparent' in m) m.transparent = true;
    if('opacity' in m) m.opacity = isFace?0.97:0.92;
    m.needsUpdate = true;
  });
}

function setMorph(name, value){
  for(let k=0;k<morphMeshes.length;k++){
    const m = morphMeshes[k];
    const i = m.morphTargetDictionary[name];
    if(i!==undefined) m.morphTargetInfluences[i] = value;
  }
}

function clearMouthMorphs(){
  if(!faceMesh) return;
  const keys = ['jawOpen','mouthOpen','mouthFunnel','mouthPucker','mouthClose'];
  keys.concat(VISEMES).forEach(k=>setMorph(k,0));
}

function tick(){
  const dt = clock ? clock.getDelta() : 0.016;
  if(mixer) mixer.update(dt);

  // Auto blink
  blinkT += dt;
  if(faceMesh && morphDict){
    if(blinkT >= nextBlinkAt){
      const phase = blinkT - nextBlinkAt;
      const v = phase < 0.07 ? phase/0.07 : (phase < 0.14 ? 1-(phase-0.07)/0.07 : 0);
      setMorph('eyeBlinkLeft', v);
      setMorph('eyeBlinkRight', v);
      if(phase > 0.14){ blinkT = 0; nextBlinkAt = 2+Math.random()*3.5; }
    }
  }

  // Head sway
  if(headBone){
    headSwayT += dt;
    const intensity = state==='speaking' ? 0.06 : (state==='thinking' ? 0.04 : 0.025);
    headBone.rotation.y = Math.sin(headSwayT*0.6)*intensity;
    headBone.rotation.x = Math.sin(headSwayT*0.42)*intensity*0.4;
  }

  // Lip-sync from audio analyser
  if(state==='speaking' && analyser && faceMesh && morphDict){
    analyser.getByteTimeDomainData(timeData);
    let sum=0;
    for(let i=0;i<timeData.length;i++){ const v=(timeData[i]-128)/128; sum += v*v; }
    const rms = Math.sqrt(sum/timeData.length);
    const target = Math.min(1, rms*4.2);
    smoothJaw += (target - smoothJaw) * Math.min(1, dt*22);

    analyser.getByteFrequencyData(freqData);
    let lo=0, mid=0, hi=0;
    const N = freqData.length;
    const a = Math.floor(N*0.04), b = Math.floor(N*0.18), c = Math.floor(N*0.55);
    for(let i=a;i<b;i++) lo += freqData[i];
    for(let i=b;i<c;i++) mid += freqData[i];
    for(let i=c;i<N;i++) hi += freqData[i];
    const tot = lo+mid+hi+1;
    const fLo = lo/tot, fMid = mid/tot, fHi = hi/tot;
    const tgtA = smoothJaw * (0.55 + 0.45*fMid);
    const tgtO = smoothJaw * (0.55 + 0.45*fLo);
    const tgtE = smoothJaw * (0.55 + 0.45*fHi);
    smoothA += (tgtA - smoothA) * Math.min(1, dt*18);
    smoothO += (tgtO - smoothO) * Math.min(1, dt*18);
    smoothE += (tgtE - smoothE) * Math.min(1, dt*18);

    setMorph('jawOpen', smoothJaw*0.85);
    setMorph('mouthOpen', smoothJaw*0.55);
    setMorph('viseme_aa', smoothA*0.75);
    setMorph('viseme_O',  smoothO*0.55);
    setMorph('viseme_E',  smoothE*0.55);
    setMorph('viseme_I',  smoothE*0.35);
    setMorph('viseme_U',  smoothO*0.30);
  } else if(faceMesh){
    smoothJaw += (0 - smoothJaw) * Math.min(1, dt*12);
    smoothA += (0 - smoothA) * Math.min(1, dt*12);
    smoothO += (0 - smoothO) * Math.min(1, dt*12);
    smoothE += (0 - smoothE) * Math.min(1, dt*12);
    if(state==='thinking'){
      const p = 0.05 + 0.04*Math.sin(performance.now()*0.004);
      setMorph('mouthPucker', p);
      setMorph('jawOpen', 0); setMorph('viseme_aa', 0);
    } else {
      setMorph('mouthPucker', 0);
      setMorph('jawOpen', smoothJaw*0.8);
      setMorph('viseme_aa', smoothA*0.7);
      setMorph('viseme_O', smoothO*0.5);
      setMorph('viseme_E', smoothE*0.5);
    }
  }

  if(renderer && scene && camera) renderer.render(scene, camera);
}

async function speakBlob(blob, onEnd){
  if(!audioCtx) audioCtx = new (window.AudioContext||window.webkitAudioContext)();
  if(audioCtx.state==='suspended') await audioCtx.resume();
  stopCurrentAudio();

  const arr = await blob.arrayBuffer();
  const buf = await audioCtx.decodeAudioData(arr.slice(0));
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  if(!analyser){
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.5;
    timeData = new Uint8Array(analyser.fftSize);
    freqData = new Uint8Array(analyser.frequencyBinCount);
  }
  src.connect(analyser);
  analyser.connect(audioCtx.destination);
  currentSource = src;
  currentEndCb = onEnd || null;
  state = 'speaking';
  src.onended = ()=>{
    if(currentSource===src){
      currentSource=null;
      state='idle';
      clearMouthMorphs();
      const cb = currentEndCb; currentEndCb = null;
      if(cb) try{cb()}catch(e){}
    }
  };
  src.start(0);
}

function stopCurrentAudio(){
  if(currentSource){
    try{ currentSource.onended=null; currentSource.stop(0); }catch(e){}
    currentSource=null;
  }
  currentEndCb=null;
  clearMouthMorphs();
}

window.Avatar3D = {
  setState(s){
    if(s==='speaking' || s==='thinking' || s==='idle') state = s;
    if(s==='idle') clearMouthMorphs();
  },
  speak(blob, onEnd){ return speakBlob(blob, onEnd); },
  stop(){ stopCurrentAudio(); state='idle'; }
};

// ── MOBILE FUNCTIONS ──
var mobChatExpanded=false;
function expandChat(){
  mobChatExpanded=!mobChatExpanded;
  var co=document.getElementById('chat-overlay');
  if(co)co.classList.toggle('expanded',mobChatExpanded);
}
function toggleMobDrawer(){
  var d=document.getElementById('mob-drawer');
  var b=document.getElementById('mob-backdrop');
  if(!d)return;
  var isOpen=d.classList.contains('open');
  d.classList.toggle('open',!isOpen);
  if(b)b.classList.toggle('active',!isOpen);
  if(isOpen) mobChatExpanded=false;
}
function closeMobDrawer(){
  var d=document.getElementById('mob-drawer');
  var b=document.getElementById('mob-backdrop');
  if(d)d.classList.remove('open');
  if(b)b.classList.remove('active');
}

// ── Mobile: update time and model in mob-bar ──
function updateMobBar(){
  var el=document.getElementById('mob-time');
  var mdl=document.getElementById('mob-model');
  var topMdl=document.getElementById('top-model');
  if(el)el.textContent=new Date().toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit'});
  if(mdl&&topMdl)mdl.textContent=topMdl.textContent;
}

// ── Mobile: tap background to dismiss keyboard ──
document.addEventListener('DOMContentLoaded',function(){
  var msgs=document.getElementById('msgs');
  if(msgs)msgs.addEventListener('click',function(){
    var inp=document.getElementById('minput');
    if(inp&&document.activeElement===inp)inp.blur();
  });
  setInterval(updateMobBar,10000);
  updateMobBar();
});

// ── Mobile: handle keyboard show/hide ──
if(window.visualViewport){
  window.visualViewport.addEventListener('resize',function(){
    var co=document.getElementById('chat-overlay');
    if(!co||window.innerWidth>480)return;
    var diff=window.innerHeight - window.visualViewport.height;
    if(diff>100){
      co.style.bottom=(diff)+'px';
    }else{
      co.style.bottom='';
    }
  });
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded', initThree);
}else{
  initThree();
}
