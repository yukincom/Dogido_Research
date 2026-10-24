/* 公開画像の参照だけを解決する。保存・貼り替え・削除の状態は持たない。 */
(function(root){
  'use strict';
  const safeUrl=value=>typeof value==='string'&&/^data\/images\/[a-f0-9]{64}\.png$/.test(value)?value:null;
  function create(snapshot={}){
    const rows=Array.isArray(snapshot.items)?snapshot.items:[];
    const items=rows.filter(p=>p&&typeof p.id==='string').map(p=>({...p,url:safeUrl(p.url)}));
    const find=id=>items.find(p=>p.id===id);
    const title=id=>find(id)?.title||'';
    const displayTitle=id=>title(id).trim()||'発句時の写真';
    const slots=target=>(snapshot.placements?.[target]||[]).filter(id=>find(id));
    const original=target=>find(snapshot.originals?.[target])||null;
    return {
      all:()=>items.map(p=>({...p,displayTitle:displayTitle(p.id)})),find,slots,original,title,displayTitle,
      mainPhoto(target,preferred){const ids=slots(target),first=original(target);return ((ids.includes(preferred)||first?.id===preferred)&&find(preferred))||first||ids.map(find).find(Boolean)||null;},
      targets(id){return [...new Set([...Object.keys(snapshot.placements||{}),...Object.keys(snapshot.originals||{})])].filter(target=>slots(target).includes(id)||original(target)?.id===id);}
    };
  }
  const api={create,safeUrl};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DogidoPhotoLibraryModel=api;
})(typeof window==='undefined'?globalThis:window);
