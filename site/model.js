(function (root) {
  'use strict';
  const categories = {all:'すべて',biome:'バイオーム',structure:'ストラクチャ',mob:'モブ',block:'ブロック',item:'アイテム'};
  // Exact biome identities and labels from data/catalogs/entries/minecraft_biome.json.
  const biomes = Object.freeze(root.DOGIDO_BOOTSTRAP?.biomes||{});
  const biomeEnglish=Object.freeze(root.DOGIDO_BOOTSTRAP?.biomeEnglish||{});
  function catalogEnglishName(id){
    id=String(id).replace(/^(biome|structure|mob|block|item):/,'');
    const names={village_plains:'Plains Village',village_desert:'Desert Village'};
    return names[id]||String(id).replace(/^minecraft:/,'').split('_').map(word=>word.charAt(0).toUpperCase()+word.slice(1)).join(' ');
  }
  const times = Object.freeze({morning:'朝',day:'昼',evening:'夕',night:'夜'});
  // 本体の投影だけを表示する。接続失敗を架空の句で補わない。
  const poems = root.DOGIDO_BOOTSTRAP?.poems||[];
  poems.forEach(poem=>{poem.biome=biomes[poem.biomeId];});
  function normalize(value){return String(value ?? '').normalize('NFKC').toLowerCase().replace(/[ァ-ヶ]/g,c=>String.fromCharCode(c.charCodeAt(0)-0x60));}
  function filterCatalog(entries,{category='all',query=''}={}){const q=normalize(query).trim();return entries.filter(e=>(category==='all'||e.category===category)&&normalize(JSON.stringify([e.raw,e.contextNotes])).includes(q));}
  // Keep entry notes and inherited classification notes separate; never invent prose.
  function catalogBasicInfo(entry){
    const raw=entry.raw,sections=[];
    // Editorial metadata and an unverified ocean-wide claim are not player prose.
    // Keep the source untouched; the review report records why these are withheld.
    const withheldBiomeText=new Set([
      'ペールガーデンは気温・降水量の記載が見当たらないため null とした。',
      '海洋はY=63までの水のみで構成された大きくて開放的なバイオーム。海底には小さな山や平原などの水中地形がある。オーバーワールドの地表の約60%は海洋に覆われている。'
    ]);
    const texts=value=>(Array.isArray(value)?value:[value]).filter(v=>typeof v==='string'&&v.trim()&&!(entry.category==='biome'&&withheldBiomeText.has(v)));
    function add(label,...values){
      const paragraphs=[...new Set(values.flatMap(texts))];
      if(paragraphs.length)sections.push({label,paragraphs});
    }
    if(entry.category==='biome'){
      add('説明',raw.note,raw.notes,raw.summary,raw.overview,raw.description,raw.environment_notes);
    }else add('説明',raw.note,raw.notes);
    add('性質・行動のメモ',raw.dogido_tactics?.notes);
    const groupValues=[raw.group_overview,raw.group_note,raw.group_notes];
    if(entry.category==='biome'){
      for(const key of ['summary','snow_rule_summary','precipitation_rule_summary','vegetation_color_summary','water_color_summary','sky_color_summary'])groupValues.push(raw[`group_${key}`]);
      // Deliberately do not recurse into Bedrock colors, command exceptions, or numeric rules.
      for(const key of ['precipitation','terrain_summary'])groupValues.push(raw.group_environment_rules?.[key]);
    }
    add(`${raw.group_label||'分類'}の共通説明`,...groupValues);
    for(const context of entry.contextNotes||[])add(`${context.label}の共通説明`,context.text);
    return sections;
  }
  function filterPoems(entries,{query='',author='all',biome='all',timeOfDay='all',period='all',poemSection='all',favoritesOnly=false,favorites=new Set()}={}){
    const q=normalize(query).trim();
    return entries.filter(e=>(author==='all'||e.author===author)
      &&(poemSection!=='player'||e.author==='プレイヤー')
      &&(biome==='all'||e.biomeId===biome)
      &&(timeOfDay==='all'||e.timeOfDay===timeOfDay)
      &&(period==='all'||e.date.startsWith(period))
      &&(!(favoritesOnly||poemSection==='favorites')||favorites.has(e.id))
      &&normalize([...e.lines,e.author,e.biome,biomeEnglish[e.biomeId],e.biomeId,times[e.timeOfDay],e.preface].join(' ')).includes(q));
  }
  function summary(e){return e.raw.note||e.raw.poetic?.role||e.raw.group_label||'カタログの基本情報をひらく';}
  const api={categories,biomes,biomeEnglish,catalogEnglishName,catalogBasicInfo,times,poems,normalize,filterCatalog,filterPoems,summary};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DogidoLibrary=api;
})(typeof window==='undefined'?globalThis:window);
