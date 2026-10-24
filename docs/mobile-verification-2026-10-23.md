# Standalone mobile beta verification

Scope: PC TV Live Android and web; PC TV Remote Android. No PC is required at runtime. Pro/Lite mobile and iPhone web Remote are not offered. Live mobile is a curated ten-channel edition without the desktop guide or full country catalogue.

## Automated checks

- Final Android release builds and Android lint passed: Live 0 errors/6 warnings; Remote 0 errors/8 warnings. Warnings cover translation strings, JavaScript enablement, deprecated/platform settings and newer tooling notices.
- 11 Remote Python tests passed, including pairing persistence, private-IP/command validation, partial discovery, power routing, Google TV event-loop dispatch and literal text encoding.
- Four Live catalogue/favorites tests and Java native URL-boundary tests passed.
- Browser integration passed at widths 320, 390, 768 and 1280: no horizontal overflow; search/categories, favorite persistence, installation help, offline cached shell, native bridge and stream-error recovery. All ten live streams decoded video in Chromium. Stream evidence: `tests/live-stream-evidence.json`.
- Both APKs verified under Android v2 signing with the same certificate SHA-256: `4c16e620bde8eccf2c7b765d797ec71b3b64beb6ec2748625efe58807c258587`. ZIP alignment checks passed. Signing material is not in this repository.

## Android 16 x86_64 emulator

- Both signed release APKs installed and launched.
- Live loaded its bundled catalogue, handed CBS News playback to the native player, and decoded 1280×720 H.264 video with AAC audio. Media player reported state 5, unpaused playback and advancing decoded frames. Playback stopped when leaving the app. Final inset fix measured the WebView within y=128–2274, with the header below the status bar.
- Remote initialized the bundled Python engine, contacted a simulated Roku at the emulator host gateway, displayed online status and sent `/keypress/Home` through the native button. Saved TV persisted across process restart; Forget removed it. The fixture is a test server standing in for a TV, not a runtime dependency of the app.

## Review and limits

Independent source review found and verified fixes for wake-capable power dispatch, Google TV asyncio thread use, literal slash encoding and Wi-Fi network binding. No critical/important findings remained.

No physical Android phone, TV, iPhone Safari or AirPlay receiver was available. Real model compatibility, iPhone home-screen behavior and AirPlay remain unverified. Emulator success is not a claim of universal device support. Android TV/Fire TV installation is not a validated target.

## Maintenance

Increment the service-worker `CACHE` version in `live/sw.js` whenever updating bundled web files or channel URLs, then rerun browser/offline tests. Cached pages otherwise retain the prior assets until a new service worker activates. Streams are external and can disappear or become region restricted.
