/* 公開本棚の固定URLを共有する。共有ボタンで選択パネルを開き、Xは投稿画面へ直接渡す。
 * リンクコピーはURLだけを使い、現在の検索語・表示中の相談・端末情報を含めない。 */
(function(){
  'use strict';
  const URL='https://yukincom.github.io/Dogido_Research/';
  const TEXT='Minecraftで川柳を詠む相棒、ドギド。\n川柳・推敲・相談の記録を、公開本棚で読めます。';

  // 画像は公開ページのカード情報として指定する。投稿への画像添付を表す偽の引数は付けない。
  function shareLink(){return 'https://x.com/intent/tweet?'+new URLSearchParams({text:TEXT,url:URL,hashtags:'ドギド,Minecraft'});}
  async function copyLink(clipboard){
    try{await clipboard.writeText(URL);return true;}
    catch{return false;}
  }
  if(typeof module==='object'&&module.exports)module.exports={shareLink,copyLink,URL};
  if(typeof window==='undefined'||typeof document==='undefined')return;

  const dialog=document.getElementById('share-dialog'),status=document.getElementById('share-status');
  const url=document.getElementById('share-url');
  url.value=URL;
  document.getElementById('share-x').href=shareLink();
  document.getElementById('share-open').addEventListener('click',()=>{
    status.textContent='';url.hidden=true;dialog.showModal();
  });
  document.getElementById('share-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{
    if(event.target!==dialog)return;
    const rect=dialog.getBoundingClientRect();
    if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();
  });
  document.getElementById('share-copy').addEventListener('click',async()=>{
    if(await copyLink(navigator.clipboard)){
      url.hidden=true;status.textContent='リンクをコピーしました。';
    }else{
      url.hidden=false;url.focus();url.select();status.textContent='このリンクをコピーしてください。';
    }
  });
})();
