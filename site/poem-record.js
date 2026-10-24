/* 公開投影に残された制作記録だけを表示する。推敲・相談・材料を保存時の項目から読み、未記録の説明を補わない。 */
(function(root){
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const texts=atoms=>(Array.isArray(atoms)?atoms:[]).map(atom=>typeof atom==='string'?atom:atom?.text).filter(text=>typeof text==='string'&&text.trim());
  function time(value){const date=new Date(value);return Number.isNaN(date.valueOf())?'時刻未記録':new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit'}).format(date);}
  function fullTime(value){const date=new Date(value);return Number.isNaN(date.valueOf())?'日時未記録':new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(date);}
  function render(e){
    const m=e.materials||{},dialogue=Array.isArray(e.dialogue)?e.dialogue:[],history=Array.isArray(e.history)?e.history:[];
    const sources=(Array.isArray(m.line_sources)?m.line_sources:[]).map(row=>({line:row.text,sources:texts(row.sources)}));
    const candidates=texts(m.source_atoms);
    const revisions=`<details><summary>推敲の記録 <span>${history.length}件</span></summary>${history.length?`<ol class="revision-history">${history.map(row=>`<li><time datetime="${esc(row.date||'')}">${fullTime(row.date)}</time><p class="revision-verse">${(Array.isArray(row.lines)?row.lines:[]).map(esc).join('<br>')}</p></li>`).join('')}</ol>`:'<p class="record-missing">保存された推敲はありません。</p>'}</details>`;
    return `<section class="poem-record" aria-label="句の制作記録">${revisions}<details open><summary>対話の記録 <span>${dialogue.length}往復</span></summary>${dialogue.length?`<ol class="workshop-dialogue">${dialogue.map(turn=>`<li><time datetime="${esc(turn.time)}" title="${esc(fullTime(turn.time))}">${fullTime(turn.time)}</time><p><b>プレイヤー</b><span>${esc(turn.player)}</span></p><p><b>ドギド</b><span>${esc(turn.dogido)}</span></p></li>`).join('')}</ol>`:'<p class="record-missing">公開された対話はありません。</p>'}</details><details><summary>発句の材料</summary>${sources.length?`<h4>行ごとの材料</h4><ul class="line-sources">${sources.map(row=>`<li><strong>${esc(row.line)}</strong><p>${row.sources.map(esc).join(' ／ ')||'材料の本文は未公開'}</p></li>`).join('')}</ul>`:''}${candidates.length?`<h4>発句時の候補材料</h4><ul>${candidates.map(text=>`<li>${esc(text)}</li>`).join('')}</ul>`:''}${m.interpretation?`<h4>発句時の解釈</h4><p class="record-prose">${esc(m.interpretation)}</p>`:''}${!sources.length&&!candidates.length&&!m.interpretation?'<p class="record-missing">公開された材料はありません。</p>':''}</details></section>`;
  }
  const api={render,time,fullTime};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DogidoPoemRecord=api;
})(typeof window==='undefined'?globalThis:window);
