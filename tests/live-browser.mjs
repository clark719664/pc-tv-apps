import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {extname, resolve, sep} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright');
const root = fileURLToPath(new URL('../live/', import.meta.url));
const mime = {'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.png':'image/png','.webmanifest':'application/manifest+json','.txt':'text/plain'};
const server = createServer(async (req,res) => {
  try {
    const pathname = new URL(req.url,'http://localhost').pathname;
    const file = resolve(root, '.' + (pathname === '/' ? '/index.html' : decodeURIComponent(pathname)));
    if (!file.startsWith(root.endsWith(sep) ? root : root + sep)) {res.writeHead(403).end();return;}
    const body = await readFile(file);
    res.writeHead(200, {'content-type':mime[extname(file)] || 'application/octet-stream','cache-control':'no-cache'}).end(body);
  } catch {res.writeHead(404).end();}
});
await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
const url = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({headless:true});
const errors = [];
try {
  const context = await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1});
  await context.addInitScript(() => { window.PCTVPlayer = {play:(url,title) => {window.nativeCall={url,title};}}; });
  const page = await context.newPage();
  page.on('pageerror',error => errors.push(error.message));
  await page.goto(url);
  await page.waitForSelector('.channel-row');
  assert.equal(await page.locator('.channel-row').count(),10);
  assert.equal(await page.locator('#screen').isVisible(),false,'native app must not show an inactive web player');
  for (const width of [320,390,768,1280]) {
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `horizontal overflow at ${width}px`);
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel('Save CBS News 24/7 to favorites',{exact:true}).click();
  await page.reload();
  assert.equal(await page.getByLabel('Remove CBS News 24/7 from favorites',{exact:true}).getAttribute('aria-pressed'),'true');
  await page.getByRole('button',{name:'♡ Favorites',exact:true}).click();
  assert.equal(await page.locator('.channel-row').count(),1);
  await page.getByLabel('Search channels',{exact:true}).fill('impossible query');
  assert.equal(await page.locator('.channel-row').count(),0);
  await page.getByRole('button',{name:'Show all channels'}).click();
  await page.getByLabel('Category',{exact:true}).selectOption('Sport');
  assert.equal(await page.locator('.channel-row').count(),2);
  await page.getByRole('button',{name:'Watch Red Bull TV',exact:true}).click();
  assert.equal(await page.evaluate(() => window.nativeCall.title),'Red Bull TV');
  assert.ok((await page.evaluate(() => window.nativeCall.url)).startsWith('https://'));
  assert.equal(await page.locator('#state-label').textContent(),'Android player');
  await page.getByLabel('Category',{exact:true}).selectOption('All');
  await page.evaluate(() => window.scrollTo(0,0));
  if (process.env.LIVE_SCREENSHOT) await page.screenshot({path:process.env.LIVE_SCREENSHOT,fullPage:true});
  console.log('PASS: 320/390/768/1280px overflow, search, categories, favorites persistence, native bridge');
  await context.close();

  const web = await browser.newContext({viewport:{width:390,height:844}});
  const webPage = await web.newPage();
  webPage.on('pageerror',error => errors.push(error.message));
  await webPage.goto(url);
  await webPage.evaluate(() => navigator.serviceWorker.ready);
  await webPage.getByRole('button',{name:'Install',exact:true}).click();
  await webPage.getByRole('heading',{name:'Keep Live on your home screen.'}).waitFor();
  await webPage.getByRole('button',{name:'Close install instructions'}).click();
  await web.setOffline(true);
  // This Chromium build blocks network traffic but leaves navigator.onLine true.
  // Model the browser's offline flag separately while testing real offline shell loads.
  await web.addInitScript(() => Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>false}));
  await webPage.reload();
  await webPage.waitForSelector('.channel-row');
  assert.equal(await webPage.locator('.channel-row').count(),10);
  assert.equal(await webPage.locator('#state-label').textContent(),'You’re offline');
  await webPage.getByRole('button',{name:'Watch CBS News 24/7',exact:true}).click();
  await webPage.getByRole('button',{name:'Try again',exact:true}).waitFor();
  const cacheUrls = await webPage.evaluate(async () => (await Promise.all((await caches.keys()).map(async key => (await (await caches.open(key)).keys()).map(r=>r.url)))).flat());
  assert.ok(cacheUrls.length >= 10);
  assert.ok(cacheUrls.every(item => item.startsWith(locationOrigin(url))));
  assert.ok(cacheUrls.every(item => !/\.m3u8|\.ts(?:\?|$)|\.mp4/.test(item)));
  await web.setOffline(false);
  await webPage.evaluate(() => {Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>true});window.dispatchEvent(new Event('online'));});
  console.log('PASS: install instructions, offline cached shell and guide, no video in cache');

  if (process.env.LIVE_PLAYBACK === '1') {
    const playbackFailures = [];
    for (const name of ['CBS News 24/7','DW English','France 24 English','NHK World-Japan','Euronews English','ABC News Australia','Red Bull TV','Outdoor America','FailArmy','The Pet Collective']) {
      await webPage.getByRole('button',{name:`Watch ${name}`,exact:true}).click();
      try {
        await webPage.waitForFunction(() => {const video=document.querySelector('video');return video.currentTime > 0 && !video.paused && video.videoWidth > 0;},null,{timeout:25000});
        console.log(`PLAYBACK PASS: ${name} ${JSON.stringify(await webPage.locator('video').evaluate(v=>({width:v.videoWidth,height:v.videoHeight,time:v.currentTime})))}`);
      } catch { playbackFailures.push(name); console.log(`PLAYBACK UNCONFIRMED: ${name}: ${await webPage.locator('#status').textContent()}`); }
      await webPage.getByRole('button',{name:'Stop',exact:true}).click();
    }
    assert.deepEqual(playbackFailures,[], 'every selected live channel must decode actual video');
  }
  await web.close();

  const failure = await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
  await failure.route('**/*.m3u8',route=>route.abort());
  const failurePage = await failure.newPage();
  failurePage.on('pageerror',error => errors.push(error.message));
  await failurePage.goto(url);
  await failurePage.getByRole('button',{name:'Watch CBS News 24/7',exact:true}).click();
  await failurePage.waitForFunction(() => document.querySelector('#state-label').textContent === 'Stream unavailable',null,{timeout:30000});
  assert.equal(await failurePage.getByRole('button',{name:'Try again',exact:true}).isVisible(),true);
  console.log('PASS: failed stream shows useful error and retry');
  await failure.close();
  assert.deepEqual(errors,[],'uncaught page errors');
  console.log('PASS: no uncaught browser errors');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
function locationOrigin(url) {return new URL(url).origin;}
