// ============================================================
// PROMPT GENERATOR v2 — dynamic word bank engine
// ============================================================
let promptBank = {};
let selectedPresets = {};

async function loadPromptBank() {
    try {
        const res = await fetch('/api/prompt-bank');
        promptBank = await res.json();
        buildPresetPanels();
    } catch(e) {
        document.getElementById('presetCategories').innerHTML = '<div style="text-align:center;color:var(--danger);padding:20px">Failed to load prompt bank</div>';
    }
}

function shuffleArray(arr) { const a = [...arr]; for (let i = a.length-1; i>0; i--) { const j = Math.floor(Math.random()*(i+1)); [a[i],a[j]] = [a[j],a[i]]; } return a; }
function pickRandom(arr) { return arr[Math.floor(Math.random()*arr.length)]; }

function buildPresetPanels() {
    const container = document.getElementById('presetCategories');
    if (!container) return;
    let html = '';
    for (const [catKey, catData] of Object.entries(promptBank)) {
        const upperKey = catKey.charAt(0).toUpperCase() + catKey.slice(1);
        html += '<div class="panel">';
        html += '<div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">';
        html += '<span>' + catData.label + '</span>';
        html += '<button onclick="shuffleCategory(\'' + catKey + '\')" style="font-size:11px;padding:3px 10px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.3);border-radius:6px;color:var(--accent);cursor:pointer">&#x1F3B2; Shuffle</button>';
        html += '</div>';
        html += '<div class="preset-row" id="chips' + upperKey + '">';
        const allTerms = [];
        for (const [, terms] of Object.entries(catData.sub)) {
            allTerms.push({label: pickRandom(terms), value: pickRandom(terms)});
        }
        for (const t of shuffleArray(allTerms).slice(0, 6)) {
            html += '<div class="preset-chip" data-group="' + catKey + '" data-val="' + t.value + '">' + t.label + '</div>';
        }
        html += '</div></div>';
    }
    container.innerHTML = html;
    bindChipEvents();
    selectedPresets = {};
    updatePreviewTags();
}

function shuffleCategory(catKey) {
    const catData = promptBank[catKey]; if (!catData) return;
    const upperKey = catKey.charAt(0).toUpperCase() + catKey.slice(1);
    const chipRow = document.getElementById('chips' + upperKey);
    if (!chipRow) return;
    const selectedVal = selectedPresets[catKey];
    const allTerms = [];
    for (const [, terms] of Object.entries(catData.sub)) {
        allTerms.push({label: pickRandom(terms), value: pickRandom(terms)});
    }
    const shuffled = shuffleArray(allTerms).slice(0, 6);
    if (selectedVal && !shuffled.find(function(t){return t.value===selectedVal})) {
        shuffled[0] = {label: selectedVal, value: selectedVal};
    }
    let chipsHtml = '';
    for (const t of shuffled) {
        const selClass = (selectedVal && t.value === selectedVal) ? ' selected' : '';
        chipsHtml += '<div class="preset-chip' + selClass + '" data-group="' + catKey + '" data-val="' + t.value + '">' + t.label + '</div>';
    }
    chipRow.innerHTML = chipsHtml;
    bindChipEvents();
    updatePreviewTags();
}

function randomizeAll() { buildPresetPanels(); showToast('All presets randomized!', 'var(--accent)'); }
function surpriseMe() {
selectedPresets = {}; const parts = [];
for (const [catKey, catData] of Object.entries(promptBank)) {
const ct = [];
for (const [, terms] of Object.entries(catData.sub)) { const p = pickRandom(terms); ct.push(p); parts.push(p); }
selectedPresets[catKey] = ct.join(', ');
}
refreshAllChips(); updatePreviewTags();
const subject = document.getElementById('promptSubject').value.trim();
document.getElementById('previewTags').textContent = (subject ? subject + ', ' : '') + parts.join(', ');
showToast('Surprise prompt! ' + parts.length + ' axis picks', 'var(--accent-cyan)');
}

function refreshAllChips() {
for (const ck of Object.keys(promptBank)) {
const uk = ck.charAt(0).toUpperCase()+ck.slice(1);
const row = document.getElementById('chips'+uk);
if(!row)continue;
const v=selectedPresets[ck]||'';
row.querySelectorAll('.preset-chip').forEach(ch=>ch.classList.toggle('selected',v&&v.indexOf(ch.dataset.val)>=0));
}
}
function bindChipEvents() {
document.querySelectorAll('.preset-chip').forEach(ch=>{ch.removeEventListener('click',chipClickHandler);ch.addEventListener('click',chipClickHandler)});
}
function chipClickHandler() {
const g=this.dataset.group;const v=this.dataset.val;
if(selectedPresets[g]===v){delete selectedPresets[g];this.classList.remove('selected')}
else{this.parentElement.querySelectorAll('.preset-chip').forEach(c=>c.classList.remove('selected'));this.classList.add('selected');selectedPresets[g]=v}
updatePreviewTags();
}
function updatePreviewTags() {
const p=Object.values(selectedPresets).filter(Boolean);
document.getElementById('previewTags').textContent=p.length?p.join(', '):'-- select presets above --';
}

async function fetchOllamaModels() {
try{
const r=await fetch('/api/ollama/models');
const d=await r.json();
const s=document.getElementById('ollamaModelSelect');
s.innerHTML=d.models.length?'':'<option value="">-- No Ollama models found --</option>';
d.models.forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=m;if(m.includes('nsfw')||m.includes('prompt'))o.selected=true;s.appendChild(o)});
}catch(e){document.getElementById('ollamaModelSelect').innerHTML='<option value="">-- Ollama offline --</option>'}
}

function buildPromptInstruction() {
const su=document.getElementById('promptSubject').value.trim();
const cx=document.getElementById('promptContext').value.trim();
const pr=Object.values(selectedPresets).filter(Boolean);
const ps=pr.length?pr.join(', '):'';
let i='You are an expert Stable Diffusion / Flux prompt engineer. Generate a detailed, evocative image generation prompt.\n\n';
if(su)i+='Subject/Scene: '+su+'\n';
if(ps)i+='Required visual tags: '+ps+'\n';
if(cx)i+='Additional context: '+cx+'\n';
i+='\nRespond ONLY with:\nPOSITIVE: [comma-separated descriptive prompt]\nNEGATIVE: [things to avoid]';
return i;
}

async function generatePrompt() {
const m=document.getElementById('ollamaModelSelect').value;
if(!m)return showToast('Select an Ollama model first.','var(--warning)');
const b=document.getElementById('generateBtn');b.disabled=true;b.innerHTML='Generating...';
document.getElementById('promptLog').textContent='Sending to Ollama ('+m+')...';
document.getElementById('promptPositive').textContent='Generating...';
document.getElementById('promptNegative').textContent='...';
try{
const r=await fetch('/api/generate-prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:m,prompt:buildPromptInstruction(),stream:false})});
if(!r.ok){const e=await r.json();throw new Error(e.error||'Generation failed')}
let ft='';
const reader=r.body.getReader();const dec=new TextDecoder();
while(true){const{done,value}=await reader.read();if(done)break;const c=dec.decode(value,{stream:true});
for(const l of c.split('\n')){if(l.startsWith('data: ')){try{const j=JSON.parse(l.slice(6));ft+=j.response||''}catch(e){}}}
}
const pm=ft.match(/POSITIVE:\s*([\s\S]*?)(?=NEGATIVE:|$)/i);
const nm=ft.match(/NEGATIVE:\s*([\s\S]*)$/i);
document.getElementById('promptPositive').textContent=(pm?pm[1].trim():ft.trim())||'(empty)';
document.getElementById('promptNegative').textContent=(nm?nm[1].trim():'')||'(none)';
document.getElementById('promptLog').textContent='Done. Model: '+m;
showToast('Prompt generated!','var(--success)');
}catch(e){document.getElementById('promptPositive').textContent='ERROR: '+e.message;
document.getElementById('promptLog').textContent='Failed: '+e.message;showToast('Failed: '+e.message,'var(--danger)')}
finally{b.disabled=false;b.textContent='\u26A1 Generate Prompt via Ollama'}
}

function copyPrompt(w){const p=document.getElementById('promptPositive').textContent;const n=document.getElementById('promptNegative').textContent;let t=w==='pos'?p:w==='neg'?n:p+'\n\nNEGATIVE: '+n;navigator.clipboard.writeText(t).then(()=>showToast('Copied!','var(--success)'))}
