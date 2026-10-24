# Standalone mobile implementation plan

**Goal:** Add useful Android APK downloads and an iPhone web app without requiring a PC.

**Architecture:** PC TV Live runs a static, installable web app directly against public stream hosts, with native Android playback in its APK. PC TV Remote embeds its existing Python brand adapters in Android and connects directly to TVs. No desktop server, owner settings, personal catalogs, or account credentials are distributed.

**Scope:** Live Android + iPhone web; Remote Android. Pro and Lite remain desktop-only because their browser extraction, conversion and PC-library features have no equivalent in this release. Remote has no iPhone web version because browser networking cannot provide the existing TV protocols. Android device/TV compatibility remains beta until real hardware validation.

**Design:** Carry forward the site's dark purple palette and red Live/orange Remote accents. Make playback, channel selection and remote controls the focus. Use clear status messages and visible mobile limitations.

## Tasks
- [ ] Live web app: channel catalogue, search/favorites, direct HTTPS HLS playback, native Safari/AirPlay path, manifest and offline shell, explicit errors and no proxy/PC requirement. Unit tests cover URL safety, malformed data and filtering; browser checks cover playback startup, offline and mobile layout.
- [ ] Remote Android: existing adapter code in a bundled Python runtime; native TV selection, discovery, pairing, saved credentials in private app storage and key controls. Tests cover validation, pairing persistence and error propagation. No exported HTTP server or JavaScript bridge.
- [ ] Android builds: SDK 36, release signing outside source, APK verification and install/runtime smoke test where a device/emulator is available. Live uses a restricted local WebView and native media player. External web pages never receive the native bridge.
- [ ] Publish verified artifacts and mobile source, checksums, license notices and explicit compatibility notes. Add only functioning download links to existing site; leave current desktop release aliases intact.

## Review focus
Untrusted catalog titles/URLs must not become code; playback failures must not remain a spinner; offline shell must not imply offline live video; pairing credentials must remain private; release artifacts must exclude owner configuration and signing keys. A built APK is not proof of working TV compatibility. Record exactly which tests ran.
