/* 公開範囲と実データの件数だけを表示する。閲覧者の行動を送信・保存しない。 */
(function(){
  'use strict';
  const boot=window.DOGIDO_BOOTSTRAP,summary=document.getElementById('publication-summary');
  if(!boot){
    summary.textContent='公開データを読み込めませんでした。ページを開き直すか、JSONをダウンロードしてください。';
    summary.setAttribute('role','alert');return;
  }
  const poems=boot.poems||[],dialogueCount=poems.reduce((sum,p)=>sum+(p.dialogue||[]).length,0),images=boot.photos?.items||[];
  summary.textContent=`${poems.length}句 · 相談・講評 ${dialogueCount}往復 · 写真 ${images.length}枚`;
  const date=new Date(boot.exportedAt||'');
  if(!Number.isNaN(date.valueOf()))summary.textContent+=` · 更新 ${new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',dateStyle:'medium'}).format(date)}`;
})();
