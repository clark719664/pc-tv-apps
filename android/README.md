# PC TV standalone Android apps

Two independent apps, with no PC connection or desktop server:

- **Live:** bundled channel picker and native Android HTTPS/HLS playback. A curated mobile catalogue, not the desktop guide or full desktop channel selection.
- **Remote:** bundled Python 3.11 and the existing TV protocol adapters, called directly from native Android controls. Pairing state stays in private app storage. No local web server.

Phone/tablet beta, Android 7+. Remote is built for arm64-v8a and x86_64; Live contains no native libraries. Android TV/Fire TV launcher use and real phone/TV compatibility are not validated by emulator tests.

## Build

Install JDK 21, Android SDK platform 36 and build tools 36.0.0, and Python 3.11. Set `JAVA_HOME` and `ANDROID_HOME` to those installations, then from this directory:

```powershell
.\gradlew.bat --no-daemon :live:assembleDebug :remote:assembleDebug
.\gradlew.bat --no-daemon :live:lintRelease :remote:lintRelease
```

On Unix use `./gradlew`. Gradle and dependency versions are pinned. The Live module bundles `../live`; it never loads a website from the developer's computer. To run Python tests from the repository root:

```powershell
py -3.11 -m unittest discover -s tests -p "remote_*.py" -v
```

## Release signing

Release signing material must stay outside the repository. Set `PCTV_SIGNING_FILE` to a Java-properties file containing `storeFile`, `storePassword`, `keyAlias`, and `keyPassword`. Use forward slashes in the key path. Then run `:live:assembleRelease :remote:assembleRelease`. Without that environment variable release outputs are unsigned and must not be published as installable downloads.

Keep the original signing key backed up privately: Android updates must use the same key. Do not put keys, passwords, private TV settings, or the developer's desktop configuration in source archives.

## Limits

No desktop web-page extraction, transcoding, PC library, multi-TV streaming or schedule guide is included in Live mobile. Unsupported or unavailable streams produce an error; no cloud relay bypasses region restrictions. The native player stops when its screen goes into the background. Safari web playback and AirPlay depend on device support and stream availability.

Remote network discovery requires Wi-Fi and can be blocked by guest-network isolation or VPNs. Select the brand and approve pairing on the TV. Manual private IPv4 entry is available. Factory-specific behavior and model compatibility require real TV tests.

Third-party notices are in `third-party-notices/` and in Python wheel metadata in the built APK. The web player ships its hls.js license in `../live/vendor/`.
