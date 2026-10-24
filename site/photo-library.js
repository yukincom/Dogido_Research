/* 本棚と同じ写真一覧・見開きを公開データから描く。ローカルAPIや元画像の変更は行わない。 */
(function(){
  'use strict';
  const model=window.DogidoPhotoLibraryModel.create(window.DOGIDO_BOOTSTRAP.photos);
  const page=$('photo-library'),activePages=new Map();
  let selected=null;
  const image=(p,classes='',lazy=false)=>p?.url?`<img class="${classes}" src="${esc(p.url)}" alt="${esc(model.displayTitle(p.id))}" ${lazy?'loading="lazy"':''}>`:'<p class="public-photo-missing">公開画像がありません。</p>';
  function pageTarget(){const entry=current();return entry?`${state.book}:${entry.id}`:null;}
  function title(id){return `<p class="research-photo-title">${esc(model.displayTitle(id))}</p><p class="research-photo-label">川柳に紐づく公開写真</p>`;}
  function related(id){
    const poems=model.targets(id).filter(target=>target.startsWith('poems:')).map(target=>M.poems.find(p=>p.id===target.slice(6))).filter(Boolean);
    return poems.length?`<div class="photo-poems">${poems.map(p=>`<div class="photo-poem"><p>${p.lines.map(esc).join('<br>')}</p><button type="button" class="link-button" data-open-photo-poem="${esc(p.id)}">句集へ →</button></div>`).join('')}</div>`:'';
  }
  function photoDetail(id){
    const p=model.find(id);if(!p)return '';
    return `${image(p,'album-large-photo')}<div class="album-photo-details">${title(id)}${related(id)}${p.url?`<a class="public-photo-download" href="${esc(p.url)}" download>写真を開く・保存する ↗</a>`:''}</div>`;
  }
  function renderAlbum(){
    const cover=$('book-cover');if(page.contains(cover))page.before(cover);
    const photos=model.all();if(!photos.some(p=>p.id===selected))selected=photos[0]?.id;
    page.innerHTML=`<div class="album-columns"><aside class="album-sidebar"><header class="album-heading"><h1>フォトブック</h1></header><h2 class="album-list-heading" id="album-list-heading">写真の一覧 <span>${photos.length}枚</span></h2><nav class="album-list" aria-labelledby="album-list-heading">${photos.map(p=>`<button class="album-row" data-album-select="${esc(p.id)}" aria-pressed="${p.id===selected}">${image(p,'',true)}<span>${esc(p.displayTitle)}</span></button>`).join('')}</nav></aside><article class="album-preview${photos.length?'':' is-empty'}" aria-label="選択した写真">${photos.length?photoDetail(selected):'<p class="album-empty">公開された写真はまだありません。</p>'}</article></div>`;
  }
  function renderPoemThumbnails(){
    document.querySelectorAll('[data-poem-thumbnail]').forEach(thumb=>{
      const target=`poems:${thumb.dataset.poemThumbnail}`,p=model.mainPhoto(target,activePages.get(target));
      thumb.replaceChildren();
      if(p?.url){const img=document.createElement('img');img.src=p.url;img.alt='';img.loading='lazy';thumb.append(img);}
    });
  }
  function renderPlaced(){
    renderPoemThumbnails();
    const target=pageTarget(),entry=current();if(!target||!entry||state.book!=='poems')return;
    const detail=$('detail'),stage=detail.querySelector('.poem-scene');if(!stage)return;
    detail.querySelectorAll('.page-photos').forEach(el=>el.remove());
    stage.replaceChildren();
    const active=model.mainPhoto(target,activePages.get(target));
    activePages.set(target,active?.id);
    stage.classList.toggle('has-player-photo',Boolean(active?.url));
    stage.innerHTML=active?image(active,'collected-photo'):'<span class="art-caption">この句の写真は未公開です</span>';
    const first=model.original(target),ids=[...new Set([first?.id,...model.slots(target)].filter(Boolean))];
    if(!ids.length)return;
    const area=document.createElement('section');area.className='page-photos';area.setAttribute('aria-label','この句の公開写真');
    area.innerHTML=(active?`<div class="placed-photo-title">${title(active.id)}</div>`:'')+`<div class="placed-photo-slots">${ids.map(id=>`<div class="placed-photo-slot"><button class="placed-photo-select" data-page-photo="${esc(id)}" aria-label="${esc(model.displayTitle(id))}" aria-pressed="${active?.id===id}">${image(model.find(id),'',true)}</button></div>`).join('')}</div>`;
    detail.querySelector('.poem-overview').after(area);
  }
  document.addEventListener('dogido-album-opened',renderAlbum);
  document.addEventListener('dogido-detail-rendered',renderPlaced);
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button)return;
    if(button.dataset.albumSelect){closeBookCover();selected=button.dataset.albumSelect;renderAlbum();[...page.querySelectorAll('[data-album-select]')].find(el=>el.dataset.albumSelect===selected)?.focus({preventScroll:true});}
    if(button.dataset.openPhotoPoem)switchBook('poems',button.dataset.openPhotoPoem);
    if(button.dataset.pagePhoto){activePages.set(pageTarget(),button.dataset.pagePhoto);renderPlaced();}
  });
  // エラーになった画像は繰返し取得せず、空の画像と読み取り不能を区別して表示する。
  document.addEventListener('error',event=>{
    const img=event.target;if(!(img instanceof HTMLImageElement)||!img.closest('#photo-library,.page-photos,.poem-scene,[data-poem-thumbnail]'))return;
    img.classList.add('public-image-failed');img.alt='写真を読み込めませんでした';
    if(img.matches('.album-large-photo,.collected-photo')){
      const note=document.createElement('p');note.className='public-photo-missing';note.setAttribute('role','status');note.textContent='写真を読み込めませんでした。時間をおいてページを開き直してください。';img.replaceWith(note);
    }
  },true);
  renderAlbum();placeBookCover();renderPlaced();
})();
