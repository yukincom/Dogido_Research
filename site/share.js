/* 確認済みフライヤーと公開本棚URLだけを共有へ渡す。現在の検索語・会話・端末情報は読まない。
 * 共有先の選択と投稿は利用者が行う。端末が画像共有に非対応なら保存とコピーを案内する。 */
(function(){
  'use strict';
  const URL='https://yukincom.github.io/Dogido_Research/';
  const TITLE='ドギドの本棚';
  const TEXT='Minecraftで川柳を詠む相棒、ドギド。\n川柳・推敲・相談の記録を、公開本棚で読めます。';
  const CAPTION=TEXT+'\n'+URL+'\n#ドギド #Minecraft';

  // 元のJPEG bytesから同期でFileを用意し、共有ボタンの操作権を非同期取得で失わない。
  function imageFile(asset,FileType,decode){
    if(!asset||asset.filename!=='dogido-flyer.jpg'||asset.type!=='image/jpeg')throw new Error('Invalid share image');
    const binary=decode(asset.base64),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
    return new FileType([bytes],asset.filename,{type:asset.type});
  }
  function payload(file){return {files:[file],title:TITLE,text:TEXT+'\n#ドギド #Minecraft',url:URL};}
  function canShare(nav,file){
    try{return Boolean(file&&typeof nav.share==='function'&&typeof nav.canShare==='function'&&nav.canShare({files:[file]}));}
    catch{return false;}
  }
  function socialLink(platform){
    if(platform==='instagram')return 'https://www.instagram.com/';
    return 'https://x.com/intent/tweet?'+new URLSearchParams({text:TEXT,url:URL,hashtags:'ドギド,Minecraft'});
  }
  // OSの完了はSNSへの投稿完了を意味しない。取消は再送せず、失敗は準備画面へ返す。
  async function handoff(nav,file){
    if(!canShare(nav,file))return 'unsupported';
    try{await nav.share(payload(file));return 'opened';}
    catch(error){return error?.name==='AbortError'?'cancelled':'failed';}
  }
  if(typeof module==='object'&&module.exports)module.exports={imageFile,payload,canShare,socialLink,handoff,CAPTION,URL};
  if(typeof window==='undefined'||typeof document==='undefined')return;

  const dialog=document.getElementById('share-dialog'),status=document.getElementById('share-status');
  const caption=document.getElementById('share-caption'),native=document.getElementById('share-native');
  const social=document.getElementById('share-social'),help=document.getElementById('share-help');
  let file=null,sharing=false;
  try{file=imageFile(window.DOGIDO_SHARE_IMAGE,window.File,window.atob);}catch{/* 保存リンクは引き続き使える。 */}
  caption.value=CAPTION;

  async function shareImage(){
    if(sharing)return;
    sharing=true;native.disabled=true;
    status.textContent='共有先を選んでください。';
    const result=await handoff(navigator,file);
    sharing=false;native.disabled=false;
    status.textContent={opened:'共有先の画面で画像・リンク・投稿文を確認してください。',cancelled:'共有を取り消しました。',unsupported:'画像を保存し、投稿文とリンクをコピーして使えます。',failed:'共有画面を開けませんでした。画像保存と投稿文コピーをご利用ください。'}[result];
  }
  document.querySelectorAll('[data-share]').forEach(button=>button.addEventListener('click',()=>{
    const platform=button.dataset.share,name=platform==='instagram'?'Instagram':'X';
    document.getElementById('share-title').textContent=name+'で本棚を共有';
    social.href=socialLink(platform);
    social.textContent=platform==='instagram'?'Instagramを開く ↗':'Xの投稿画面を開く ↗';
    const supported=canShare(navigator,file);native.hidden=!supported;
    help.textContent=supported
      ?'端末の共有先から'+name+'を選んでください。アプリに投稿文が渡らない場合は、下のコピーも使えます。'
      :platform==='instagram'
        ?'画像を保存して、Instagramの「作成」で選んでください。投稿文とリンクはコピーして貼り付けられます。'
        :'Xの投稿画面に投稿文とリンクを入れて開きます。画像も添付する場合は、保存したフライヤーを選んでください。';
    status.textContent='';dialog.showModal();
  }));
  native.addEventListener('click',()=>void shareImage());
  document.getElementById('share-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{
    if(event.target!==dialog)return;
    const rect=dialog.getBoundingClientRect();
    if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();
  });
  document.getElementById('share-copy').addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(CAPTION);status.textContent='投稿文とリンクをコピーしました。';}
    catch{caption.focus();caption.select();status.textContent='投稿文を選択しました。端末のコピー操作を使ってください。';}
  });
})();
