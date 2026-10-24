import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CHANNELS, isPlayableUrl, filterChannels, readFavorites, saveFavorites } from '../live/catalog.mjs';

test('catalog has unique IDs and verified HTTPS HLS sources', () => {
  assert.ok(CHANNELS.length >= 8);
  assert.equal(new Set(CHANNELS.map(c => c.id)).size, CHANNELS.length);
  for (const channel of CHANNELS) {
    assert.equal(isPlayableUrl(channel.url), true, channel.name);
    assert.ok(channel.website.startsWith('https://'));
    assert.ok(channel.category && channel.language && channel.source);
  }
});

test('playback permits only exact curated HTTPS URLs', () => {
  assert.equal(isPlayableUrl(CHANNELS[0].url), true);
  for (const url of ['http://localhost/stream.m3u8','https://example.com/test.m3u8','javascript:alert(1)',
    CHANNELS[0].url + '?token=arbitrary', CHANNELS[0].url.replace('https://','http://'), null, '']) {
    assert.equal(isPlayableUrl(url), false);
  }
});

test('search is case insensitive and intersects category and favorites', () => {
  const first = CHANNELS[0];
  assert.ok(filterChannels(CHANNELS, {query: first.name.toUpperCase()}).some(c => c.id === first.id));
  assert.deepEqual(filterChannels(CHANNELS, {favoritesOnly: true, favorites: new Set([first.id])}), [first]);
  assert.deepEqual(filterChannels(CHANNELS, {query: 'unfindable-channel-983'}), []);
  assert.ok(filterChannels(CHANNELS, {category: 'News'}).every(c => c.category === 'News'));
  assert.deepEqual(filterChannels(CHANNELS, {category: 'Sport', favoritesOnly: true, favorites: new Set([first.id])}), []);
});

test('favorites reject corrupt storage and unknown IDs without breaking the app', () => {
  assert.deepEqual([...readFavorites({getItem: () => '{bad'})], []);
  assert.deepEqual([...readFavorites({getItem: () => 'null'})], []);
  assert.deepEqual([...readFavorites({getItem: () => '{"0":"x"}'})], []);
  assert.deepEqual([...readFavorites({getItem: () => { throw Error('blocked'); }})], []);
  assert.deepEqual([...readFavorites({getItem: () => JSON.stringify([CHANNELS[0].id, CHANNELS[0].id, 'bad'])})], [CHANNELS[0].id]);
  assert.equal(saveFavorites(new Set([CHANNELS[0].id]), {setItem: () => {throw Error('quota');}}), false);
  let saved;
  assert.equal(saveFavorites(new Set([CHANNELS[0].id]), {setItem: (key, value) => saved = value}), true);
  assert.deepEqual(JSON.parse(saved), [CHANNELS[0].id]);
});
