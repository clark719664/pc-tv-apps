import {CHANNELS, filterChannels, isPlayableUrl, readFavorites, saveFavorites} from './catalog.mjs';

const $ = id => document.getElementById(id);
const video = $('video');
let storage;
try { storage = window.localStorage; } catch { /* Favorites remain usable for this visit. */ }
const favorites = readFavorites(storage);
let selected = null;
let hls = null;
let generation = 0;
let loadTimer;
let state = 'idle';
let favoritesOnly = false;
let installPrompt;
const labels = {idle:'Ready to watch',loading:'Connecting',playing:'Live',paused:'Paused',error:'Stream unavailable',offline:'You’re offline',native:'Android player',stopped:'Stopped'};

function setStatus(next, message) {
  state = next;
  $('state-label').textContent = labels[next];
  $('state-dot').dataset.state = next;
  $('status').textContent = message;
  $('retry').hidden = !selected || !['error','offline','paused'].includes(next);
}

function renderChannels() {
  const list = filterChannels(CHANNELS, {query:$('search').value, category:$('category').value, favoritesOnly, favorites});
  $('count').textContent = `${list.length} channel${list.length === 1 ? '' : 's'}`;
  $('clear').hidden = !$('search').value;
  $('empty').hidden = list.length > 0;
  $('empty-message').textContent = favoritesOnly && favorites.size === 0 ? 'Tap a channel’s heart to save your favorites here.' : 'Try a different search or category.';
  const fragment = document.createDocumentFragment();
  for (const channel of list) {
    const row = document.createElement('article');
    row.className = `channel-row${selected?.id === channel.id ? ' selected' : ''}`;
    const play = document.createElement('button');
    play.type = 'button';
    play.className = 'channel-play';
    play.dataset.play = channel.id;
    play.setAttribute('aria-label', `Watch ${channel.name}`);
    if (selected?.id === channel.id) play.setAttribute('aria-current','true');
    const logo = document.createElement('span');
    logo.className = `channel-logo${channel.short.length > 4 ? ' long' : ''}`;
    logo.setAttribute('aria-hidden','true');
    logo.textContent = channel.short;
    const copy = document.createElement('span');
    copy.className = 'channel-copy';
    const title = document.createElement('strong');
    title.className = 'channel-title';
    title.textContent = channel.name;
    const meta = document.createElement('span');
    meta.className = 'channel-meta';
    meta.textContent = `${channel.category} · ${channel.country}`;
    copy.append(title, meta);
    const arrow = document.createElement('span');
    arrow.className = 'channel-arrow';
    arrow.setAttribute('aria-hidden','true');
    arrow.textContent = '▶';
    play.append(logo, copy, arrow);
    const favorite = document.createElement('button');
    favorite.type = 'button';
    favorite.className = 'favorite';
    favorite.dataset.favorite = channel.id;
    favorite.setAttribute('aria-pressed', String(favorites.has(channel.id)));
    favorite.setAttribute('aria-label', `${favorites.has(channel.id) ? 'Remove' : 'Save'} ${channel.name} ${favorites.has(channel.id) ? 'from' : 'to'} favorites`);
    favorite.textContent = favorites.has(channel.id) ? '♥' : '♡';
    row.append(play, favorite);
    fragment.append(row);
  }
  $('channel-list').replaceChildren(fragment);
}

function releasePlayer() {
  generation += 1;
  clearTimeout(loadTimer);
  if (hls) { hls.destroy(); hls = null; }
  video.pause();
  video.removeAttribute('src');
  video.load();
}

function playbackFailed(message) {
  clearTimeout(loadTimer);
  setStatus(navigator.onLine ? 'error' : 'offline', navigator.onLine ? message : 'Reconnect to the internet, then tap Try again. Live video is not stored offline.');
}

function watchLoadTimeout(token) {
  clearTimeout(loadTimer);
  loadTimer = setTimeout(() => {
    if (token === generation && state === 'loading') playbackFailed('This stream is taking too long. Try again, choose another channel, or visit the broadcaster.');
  }, 25000);
}

function requestPlay(token) {
  const promise = video.play();
  promise?.catch(error => {
    if (token !== generation) return;
    clearTimeout(loadTimer);
    if (error.name === 'NotAllowedError') setStatus('paused', 'Tap Play in the video controls to start. Your browser requires another tap.');
    else if (error.name !== 'AbortError') playbackFailed('This channel could not start. Try again or open its broadcaster website.');
  });
}

function playChannel(channel) {
  if (!channel || !isPlayableUrl(channel.url)) return;
  releasePlayer();
  selected = channel;
  const token = generation;
  $('now-title').textContent = channel.name;
  $('now-description').textContent = channel.description;
  $('source-link').href = channel.website;
  $('source-link').hidden = false;
  $('stop').hidden = false;
  $('welcome').hidden = true;
  renderChannels();
  (window.PCTVPlayer ? $('now-title') : $('screen')).scrollIntoView({behavior:'instant', block:'start'});
  if (!navigator.onLine) {
    playbackFailed('');
    return;
  }
  if (typeof window.PCTVPlayer?.play === 'function') {
    try {
      window.PCTVPlayer.play(channel.url, channel.name);
      $('stop').hidden = true;
      setStatus('native', 'Opened the Android player. Return here to choose another channel.');
      return;
    } catch {
      playbackFailed('The Android player could not open. Try again.');
      return;
    }
  }
  setStatus('loading', 'Opening the live stream…');
  watchLoadTimeout(token);
  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    // Safari uses native HLS, including its own AirPlay and full-screen controls.
    video.src = channel.url;
    requestPlay(token);
  } else if (window.Hls?.isSupported()) {
    hls = new window.Hls({maxBufferLength:20, backBufferLength:15, enableWorker:true});
    hls.on(window.Hls.Events.ERROR, (_event, data) => {
      if (token !== generation || !data.fatal) return;
      hls?.destroy();
      hls = null;
      playbackFailed('The stream is unavailable here, blocked by the broadcaster, or unsupported by this browser. Try another channel or the broadcaster website.');
    });
    hls.on(window.Hls.Events.MANIFEST_PARSED, () => { if (token === generation) requestPlay(token); });
    hls.loadSource(channel.url);
    hls.attachMedia(video);
  } else {
    playbackFailed('This browser cannot play HLS live video. Open this app in Safari on iPhone, a current Chrome or Edge browser, or use the broadcaster website.');
  }
}

$('channel-list').addEventListener('click', event => {
  const play = event.target.closest('[data-play]');
  if (play) playChannel(CHANNELS.find(channel => channel.id === play.dataset.play));
  const favorite = event.target.closest('[data-favorite]');
  if (favorite) {
    const id = favorite.dataset.favorite;
    favorites.has(id) ? favorites.delete(id) : favorites.add(id);
    if (!saveFavorites(favorites, storage)) {
      $('storage-status').hidden = false;
      $('storage-status').textContent = 'Your browser blocked saving. Favorites will last only for this visit.';
    }
    renderChannels();
    const replacement = document.querySelector(`[data-favorite="${id}"]`);
    (replacement || $('favorites')).focus({preventScroll:true});
  }
});
$('search').addEventListener('input', renderChannels);
$('category').addEventListener('change', renderChannels);
$('clear').addEventListener('click', () => { $('search').value = ''; renderChannels(); $('search').focus(); });
$('favorites').addEventListener('click', () => {
  favoritesOnly = !favoritesOnly;
  $('favorites').setAttribute('aria-pressed', String(favoritesOnly));
  $('favorites').textContent = favoritesOnly ? '♥ Favorites' : '♡ Favorites';
  renderChannels();
});
$('reset').addEventListener('click', () => {
  $('search').value = '';
  $('category').value = 'All';
  favoritesOnly = false;
  $('favorites').setAttribute('aria-pressed','false');
  $('favorites').textContent = '♡ Favorites';
  renderChannels();
});
$('retry').addEventListener('click', () => playChannel(selected));
$('stop').addEventListener('click', () => {
  releasePlayer();
  $('stop').hidden = true;
  setStatus('stopped', 'Playback stopped. Choose a channel to watch again.');
});
video.addEventListener('playing', () => {
  if (!selected || ['stopped','native'].includes(state)) return;
  clearTimeout(loadTimer);
  setStatus('playing', 'Watching live. Use the video controls for volume and full screen.');
});
video.addEventListener('waiting', () => {
  if (state === 'playing') {
    setStatus('loading', 'Buffering… The stream will resume when more video arrives.');
    watchLoadTimeout(generation);
  }
});
video.addEventListener('pause', () => { if (state === 'playing') setStatus('paused', 'Paused. Tap Play to continue, or Try again to return to the live stream.'); });
video.addEventListener('error', () => {
  if (selected && video.getAttribute('src') && state !== 'stopped') playbackFailed('This stream could not be loaded. It may be offline or unavailable in your region. Try another channel.');
});
video.addEventListener('ended', () => { if (selected) playbackFailed('The broadcaster ended this stream. Try again later or choose another channel.'); });
video.addEventListener('webkitplaybacktargetavailabilitychanged', event => {
  $('airplay').hidden = event.availability !== 'available' || typeof video.webkitShowPlaybackTargetPicker !== 'function';
});
$('airplay').addEventListener('click', () => { try { video.webkitShowPlaybackTargetPicker?.(); } catch { /* Native controls remain available. */ } });
window.addEventListener('offline', () => setStatus('offline','You’re offline. Favorites and the guide still work; live video needs internet.'));
window.addEventListener('online', () => {
  if (state === 'offline') setStatus(selected ? 'paused' : 'idle', selected ? 'You’re back online. Tap Try again to reconnect.' : 'You’re back online. Choose a channel to watch.');
});
window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; });
window.addEventListener('appinstalled', () => { $('install').hidden = true; });
$('install').addEventListener('click', async () => {
  if (installPrompt) { await installPrompt.prompt(); installPrompt = null; }
  else $('install-dialog').showModal();
});
if (window.PCTVPlayer || window.matchMedia('(display-mode: standalone)').matches || navigator.standalone) $('install').hidden = true;
if (window.PCTVPlayer) {
  $('player-tip').textContent = 'Channels open in the Android video player. Use Back to return to the guide.';
  $('screen').hidden = true;
  document.querySelector('.watch').classList.add('native');
}
if ('serviceWorker' in navigator && window.isSecureContext && !window.PCTVPlayer) {
  navigator.serviceWorker.register('./sw.js', {scope:'./'}).catch(() => {
    $('storage-status').hidden = false;
    $('storage-status').textContent = 'Offline app storage is unavailable in this browser. You can still watch while online.';
  });
}
renderChannels();
if (!navigator.onLine) setStatus('offline','You’re offline. Favorites and the guide still work; live video needs internet.');
