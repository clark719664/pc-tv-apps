// Public broadcaster/platform feeds selected from the iptv-org API on 2026-10-24 UTC.
// This is a reviewed starter selection, not the desktop application's catalogue.
export const CHANNELS = Object.freeze([
  { id: 'cbs-news', name: 'CBS News 24/7', short: 'CBS', category: 'News', language: 'English', country: 'United States', description: 'Breaking news and live reporting from CBS News.', website: 'https://www.cbsnews.com/live/', source: 'CBS News', url: 'https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8' },
  { id: 'dw-english', name: 'DW English', short: 'DW', category: 'News', language: 'English', country: 'Germany', description: 'World news and perspectives from Germany.', website: 'https://www.dw.com/en/live-tv/channel-english', source: 'DW / Akamai', url: 'https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/master.m3u8' },
  { id: 'france24-english', name: 'France 24 English', short: 'F24', category: 'News', language: 'English', country: 'France', description: 'International news and analysis from Paris.', website: 'https://www.france24.com/en/live', source: 'France 24', url: 'https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_900.m3u8' },
  { id: 'nhk-world', name: 'NHK World-Japan', short: 'NHK', category: 'News', language: 'English', country: 'Japan', description: 'News, culture and documentaries from Japan.', website: 'https://www3.nhk.or.jp/nhkworld/', source: 'NHK World', url: 'https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8' },
  { id: 'euronews-english', name: 'Euronews English', short: 'euronews', category: 'News', language: 'English', country: 'France', description: 'European and international news coverage.', website: 'https://www.euronews.com/live', source: 'Euronews / Akamai', url: 'https://cdn-euronews.akamaized.net/live/eds/euronews-en/25002/index.m3u8' },
  { id: 'abc-australia', name: 'ABC News Australia', short: 'ABC', category: 'News', language: 'English', country: 'Australia', description: 'Australia’s public broadcaster, live news coverage.', website: 'https://www.abc.net.au/news/newschannel/', source: 'ABC Australia / Akamai', url: 'https://abc-news-dmd-streams-1.akamaized.net/out/v1/701126012d044971b3fa89406a440133/index.m3u8' },
  { id: 'redbull', name: 'Red Bull TV', short: 'RB', category: 'Sport', language: 'English', country: 'Austria', description: 'Action sports, adventure and event programming.', website: 'https://www.redbull.com/int-en/live', source: 'Red Bull Media Network / Akamai', url: 'https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8' },
  { id: 'outdoor-america', name: 'Outdoor America', short: 'OA', category: 'Sport', language: 'English', country: 'United States', description: 'Fishing, hunting and the outdoor life.', website: 'https://www.outdooramerica.tv/', source: 'Frequency / Xumo', url: 'https://linear-600.frequency.stream/dist/xumo/600/hls/master/playlist.m3u8' },
  { id: 'failarmy', name: 'FailArmy', short: 'FA', category: 'Entertainment', language: 'English', country: 'United Kingdom feed', description: 'Funny moments and mishaps. Some content is for mature viewers.', website: 'https://www.failarmy.com/', source: 'Wurl / Samsung', url: 'https://failarmy-international-gb.samsung.wurl.tv/playlist.m3u8' },
  { id: 'pet-collective', name: 'The Pet Collective', short: 'TPC', category: 'Entertainment', language: 'English', country: 'United Kingdom feed', description: 'Animal antics and pet videos around the clock.', website: 'https://www.thepetcollective.com/streaming/', source: 'Wurl / Samsung', url: 'https://the-pet-collective-international-gb.samsung.wurl.tv/playlist.m3u8' },
].map(Object.freeze));

const approved = new Set(CHANNELS.map(channel => channel.url));
const knownIds = new Set(CHANNELS.map(channel => channel.id));
const FAVORITES_KEY = 'pctv-live-favorites-v1';

export function isPlayableUrl(url) {
  return typeof url === 'string' && url.startsWith('https://') && approved.has(url);
}

export function filterChannels(channels, {query = '', category = 'All', favoritesOnly = false, favorites = new Set()} = {}) {
  const term = String(query).trim().toLocaleLowerCase();
  return channels.filter(channel =>
    (!category || category === 'All' || channel.category === category) &&
    (!favoritesOnly || favorites.has(channel.id)) &&
    (!term || `${channel.name} ${channel.category} ${channel.country} ${channel.description}`.toLocaleLowerCase().includes(term)));
}

export function readFavorites(storage) {
  try {
    const value = JSON.parse(storage?.getItem(FAVORITES_KEY) || '[]');
    return new Set(Array.isArray(value) ? value.filter(id => knownIds.has(id)) : []);
  } catch { return new Set(); }
}

export function saveFavorites(favorites, storage) {
  try {
    if (!storage) return false;
    storage.setItem(FAVORITES_KEY, JSON.stringify([...favorites].filter(id => knownIds.has(id))));
    return true;
  } catch { return false; }
}
