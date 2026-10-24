'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const share=require('../site/share.js');

test('X opens its composer with the public URL and introduction only',()=>{
  const x=new URL(share.shareLink());
  assert.equal(x.origin,'https://x.com');assert.equal(x.pathname,'/intent/tweet');
  assert.equal(x.searchParams.get('url'),'https://yukincom.github.io/Dogido_Research/');
  assert.match(x.searchParams.get('text'),/川柳/);
  assert.deepEqual([...x.searchParams.keys()].sort(),['hashtags','text','url']);
});

test('link copy contains just the public URL and reports clipboard failure',async()=>{
  let copied;
  assert.equal(await share.copyLink({writeText:async text=>{copied=text;}}),true);
  assert.equal(copied,'https://yukincom.github.io/Dogido_Research/');
  assert.equal(await share.copyLink(undefined),false);
  assert.equal(await share.copyLink({writeText:async()=>{throw new Error('denied');}}),false);
});
