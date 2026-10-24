# PC TV Live mobile

This folder is a standalone static web app. Serve it over HTTPS to install it on iPhone or Android. It requires no PC, home server, account, private configuration, backend proxy, or desktop process. All runtime assets, including hls.js and icons, are inside this folder. Relative URLs also support hosting under a subdirectory.

## Included

- Ten curated English-language channels: CBS News 24/7, DW English, France 24 English, NHK World-Japan, Euronews English, ABC News Australia, Red Bull TV, Outdoor America, FailArmy, and The Pet Collective.
- Search by name, country, category, or description; category filter; favorites stored on the device. Corrupt or blocked storage does not prevent use.
- Native HTML video/HLS on Safari, inline/full-screen playback and native AirPlay controls. The AirPlay button appears when Safari reports an available target.
- Locally vendored hls.js 1.7.3 for MediaSource browsers. A browser without either supported route receives an actionable message and a broadcaster link.
- Actual connecting, playing, paused, buffering, timeout, stopped, unavailable, and offline states. Retry releases the previous player before opening the selected channel again.
- iPhone Safari installation instructions and browser install prompt when available.
- Manifest scope/start URL `./`. Service worker caches only an explicit list of local app-shell resources. It never intercepts third-party URLs, playlists, video segments, range requests, or arbitrary URLs. Offline use is limited to the guide and favorites.
- Android integration: `window.PCTVPlayer.play(url, title)` is called directly from a user channel action. Only exact curated URLs pass the app allowlist. The Android wrapper must also validate the URL. Native mode hides the entire HTML video screen, uses compact status controls, and skips service-worker registration.

## Sources and dependency

Channel identities and public URLs were selected from `https://iptv-org.github.io/api/channels.json` and `https://iptv-org.github.io/api/streams.json`. These APIs are discovery sources, not licensing claims. The shipped catalogue uses exact broadcaster/CDN or recognized distribution-platform feeds, excluding arbitrary relays, required custom headers, private streams and signed query-string URLs. It does not fetch the whole public directory at runtime. Country labels refer to broadcaster origin or identified feed, not availability guarantees.

The Reuters candidate was omitted because its first manifest response lacked a CORS header, despite successful server-side media retrieval. Every shipped stream passed actual Chromium decoding as well as HTTP checks. Public source availability can change after these checks; an app update is needed to change the curated list.

hls.js source: https://github.com/video-dev/hls.js/releases/tag/v1.7.3

Vendored file: `vendor/hls-1.7.3.min.js`, retrieved from `https://cdn.jsdelivr.net/npm/hls.js@1.7.3/dist/hls.min.js`.

SHA-256: `a12e7ee1cd64a69dcdb314157e45dafcba705bfb0b1440b7935cb265d374423e`

License: `vendor/hls-LICENSE.txt` (Apache 2.0), retrieved from the upstream v1.7.3 tag. App icons were copied from the existing PC TV Live brand assets at their native sizes.

## Verification

Run the pure tests with `node --test tests/live-catalog.test.mjs` from the repository root. Four tests cover catalogue integrity, exact HTTPS playback allowlist, intersecting search/category/favorite filters, and malformed/blocked favorite storage. The test was first observed failing before the implementation existed, then passing.

Run `node tests/live-browser.mjs` with Playwright and Chromium available. If Playwright is outside the repository, set `PLAYWRIGHT_MODULE` to its absolute `index.mjs` path. Set `LIVE_PLAYBACK=1` to exercise all real streams. This test starts and stops a temporary local server itself. Optional `LIVE_SCREENSHOT` writes a phone-width screenshot.

Verified on 2026-10-24 UTC / 2026-10-23 America/New_York:

- All four pure tests passed.
- No horizontal overflow at widths 320, 390, 768, and 1280 pixels; 390-pixel phone layout visually reviewed.
- Search, category filtering, favorite persistence after reload, clear/reset, and native bridge call passed.
- Native mode's HTML player is hidden (regression assertion observed failing, then passing).
- Install instructions opened; cached guide reloaded with network disabled; only the local shell was present in Cache Storage.
- This Chromium runtime does not update `navigator.onLine` when Playwright disables network. Offline UI testing therefore also models that flag explicitly; offline shell reloading still uses genuinely blocked browser network traffic.
- Blocked playlist requests produced the unavailable message and visible retry button.
- No uncaught browser errors.
- All ten channels rendered decoded video with nonzero video dimensions, advancing current time, and a non-paused video element in Chromium. Tests fail if any stream cannot be confirmed. The first decoded frame verifies playback starts, not hours of uninterrupted streaming.
- Independent playlist -> child playlist -> media requests succeeded with CORS on each shipped feed. Summary is in `tests/live-stream-evidence.json`; raw media URLs and temporary test data remain outside the app.

## Limits

This is a useful starter catalogue, not parity with the desktop catalogue. Channels can be region-restricted, change URLs, carry ads, or be temporarily unavailable. FailArmy can include mature content. This app cannot bypass provider restrictions.

No desktop media library, scheduled recording, program guide listings, local file server, Roku remote, or Chromecast sender is included. Native AirPlay depends on the Apple device, compatible receiver and network. Playback consumes mobile data. Actual iPhone Safari installation/playback and an AirPlay receiver were not available for physical-device verification. Native Android playback is handled and tested separately by the Android wrapper work.

Deployment is separate: no publication, account changes, commits, or releases were performed by this app implementation task. On a future shell update, change the service-worker cache version so installed copies receive the new app files.
