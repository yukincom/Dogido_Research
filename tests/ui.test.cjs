'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),site=path.join(root,'site');
const record=require('../site/poem-record.js'),photos=require('../site/photo-library-model.js');

test('public record escapes workshop, revision, and material text',()=>{
  const attack='<img src=x onerror=alert(1)>';
  const html=record.render({history:[{date:'2026-10-23T00:00:00Z',lines:[attack,'二行','三行']}],dialogue:[{time:'2026-10-23T00:00:00Z',player:attack,dogido:'応答'}],materials:{interpretation:attack,source_atoms:[{text:attack}],line_sources:[{text:attack,sources:[{text:attack}]}]}});
  assert.doesNotMatch(html,/<img|onerror=alert\(1\)>/);
  assert.match(html,/&lt;img/);
  assert.match(html,/推敲の記録/);assert.match(html,/1件/);assert.match(html,/1往復/);
});

test('missing records remain missing',()=>{
  const html=record.render({});
  assert.match(html,/保存された推敲はありません/);
  assert.match(html,/公開された対話はありません/);
  assert.match(html,/公開された材料はありません/);
  assert.equal(record.fullTime('bad'),'日時未記録');
});

test('photos resolve original and placement without mutation methods or remote URLs',()=>{
  const url='data/images/'+'a'.repeat(64)+'.png';
  const model=photos.create({items:[{id:'a',url,title:'写真'},{id:'b',url:'https://private.example/image.png'}],placements:{'poems:p':['a',null,'unknown']},originals:{'poems:p':'a'}});
  assert.equal(model.mainPhoto('poems:p').url,url);
  assert.deepEqual(model.targets('a'),['poems:p']);
  assert.deepEqual(model.slots('poems:p'),['a']);
  assert.equal(model.find('b').url,null);
  for(const key of ['save','attach','detach','rename','changes','accept'])assert.equal(model[key],undefined);
  for(const invalid of ['../private.png','//example.org/a.png','data:image/png;base64,ABC','data/images/../../../x.png','data/images/'+ 'a'.repeat(64)+'.png?secret'])assert.equal(photos.safeUrl(invalid),null);
});

test('shipped entrypoint loads no local editing or live API code',()=>{
  const html=fs.readFileSync(path.join(site,'index.html'),'utf8');
  const scripts=[...html.matchAll(/<script defer src="([^"]+)"/g)].map(m=>m[1]);
  assert.ok(scripts.includes('bootstrap.js'));
  for(const name of scripts.filter(name=>name!=='bootstrap.js')){
    const body=fs.readFileSync(path.join(site,name),'utf8');
    assert.doesNotMatch(body,/fetch\(|\/api\/|X-Dogido|webkit|setInterval\(|localStorage|sessionStorage/);
  }
  assert.doesNotMatch(html,/poem-editor|live-library|research-settings|bookshelf-controls|photo-picker|catalog-player-notes/);
  for(const file of [...html.matchAll(/(?:href|src)="([^"#]+)"/g)].map(m=>m[1]).filter(name=>!name.startsWith('https:')&&!['bootstrap.js','data/research.json'].includes(name)))assert.ok(fs.existsSync(path.join(site,file)),file);
});
