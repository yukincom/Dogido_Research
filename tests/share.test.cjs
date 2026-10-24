'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const share=require('../site/share.js');
const site=path.join(__dirname,'../site');

test('native sharing passes the exact approved JPEG and only public content',async()=>{
  const context={window:{}};
  vm.runInNewContext(fs.readFileSync(path.join(site,'share-image.js'),'utf8'),context);
  const file=share.imageFile(context.window.DOGIDO_SHARE_IMAGE,File,atob);
  assert.equal(file.type,'image/jpeg');assert.equal(file.name,'dogido-flyer.jpg');
  assert.deepEqual(Buffer.from(await file.arrayBuffer()),fs.readFileSync(path.join(site,'assets/dogido-flyer.jpg')));
  let received;
  const nav={canShare:data=>data.files[0]===file,share:data=>{received=data;return Promise.resolve();}};
  assert.equal(await share.handoff(nav,file),'opened');
  assert.equal(received.url,'https://yukincom.github.io/Dogido_Research/');
  assert.equal(received.files[0],file);assert.match(received.text,/Minecraft/);
  assert.deepEqual(Object.keys(received).sort(),['files','text','title','url']);
});

test('cancelled or blocked sharing never retries or claims a post succeeded',async()=>{
  for(const name of ['AbortError','NotAllowedError','DataError']){
    let calls=0;
    const nav={canShare:()=>true,share:async()=>{calls++;throw Object.assign(new Error('test'),{name});}};
    assert.equal(await share.handoff(nav,{}),name==='AbortError'?'cancelled':'failed');
    assert.equal(calls,1);
  }
  for(const nav of [{},{canShare:()=>false,share:()=>assert.fail('unsupported')},{canShare:()=>{throw new Error('blocked');},share:()=>assert.fail('blocked')}]){
    assert.equal(await share.handoff(nav,{}),'unsupported');
  }
});

test('share starts in the click task without awaiting image I/O',async()=>{
  let called=false;
  const result=share.handoff({canShare:()=>true,share:()=>{called=true;return Promise.resolve();}},{});
  assert.equal(called,true);
  assert.equal(await result,'opened');
});

test('fallback links prepare a post and never encode an invented image upload',()=>{
  const x=new URL(share.socialLink('x'));
  assert.equal(x.origin,'https://x.com');assert.equal(x.pathname,'/intent/tweet');
  assert.equal(x.searchParams.get('url'),share.URL);assert.match(x.searchParams.get('text'),/川柳/);
  assert.deepEqual([...x.searchParams.keys()].sort(),['hashtags','text','url']);
  assert.equal(share.socialLink('instagram'),'https://www.instagram.com/');
  assert.ok(share.CAPTION.includes(share.URL));
});
