# Standalone mobile beta verification

## Remote beta 3 update (2026-10-24)

The previous scan flow remembered only the TV selected from its results, so the saved-TV dropdown could contain just one TV even after discovering several. Scanning now merges every discovered TV into the saved list, preserving existing IDs, pairing details and TVs absent from a later scan. An explicit Choose TV dialog replaces the saved-TV Spinner. Run Find TVs again after updating to populate the list from a prior scan.

- 20 backend tests pass, including all discovered TVs surviving a reload, routing a command to the second TV, duplicate suppression, and preserving pairing details and unseen TVs after repeated/interrupted discovery.
- The signed release APK passes Android build/lint (0 errors, 13 warnings), v2 signature verification with the existing signer, and 16KB ZIP alignment.
- Android 16 emulator: two TVs added, both appear in the picker, switching works in both directions, the active selection and full list survive process restart, and the picker remains usable after a network status request. Regression script: `tests/remote-selector-android.py`.
- Independent focused review found no important issues. Physical-phone confirmation remains with the user. Live and the existing command transport are unchanged.

## Remote beta 2 update

Remote versionCode 2 adds a handheld remote layout with a circular D-pad, volume/channel rockers, playback controls, and a separate scrollable TVs setup panel. The existing command transport remains in place. Roku Input now lists the TV's configured inputs and launches the chosen input; duplicate friendly names include HDMI port numbers. Streaming sticks with no TV inputs receive an explicit explanation.

- Remote release build and lint pass: 0 errors, 11 warnings (translation strings and intentional physical left/right D-pad placement).
- All 18 Python tests pass, including input discovery, selection, unsafe identifiers, removed inputs, malformed responses and unsupported devices.
- Android 16 emulator tests pass for setup, online status, Home, choosing HDMI 3 among identically named Xbox inputs, saved-TV persistence, and forgetting a TV.
- Layout inspected at 411dp width and 320dp width with font scale 1.3. Playback and text labels were adjusted after inspection. The TVs panel can scroll to its lower actions at 640x320dp with font scale 1.3.
- APK v2 signature and 16KB ZIP alignment pass, with the same signer as beta 1, allowing installation over the previous APK.
- A real Roku TV returned five configured inputs during a read-only network check. No physical input switch was performed; end-to-end input switching was exercised against a local test fixture. The user reports that the previous Remote APK controls their TV quickly.
- Focused independent review found a setup-dialog scrolling issue, corrected with a ScrollView. No other important findings were reported.

The following sections record the initial beta 1 verification. Live is unchanged in beta 2.

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
