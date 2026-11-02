# Mobile simplicity pass — 2026-11-02

The mobile surfaces now use a shared near-black, neutral and blue palette with system typography. Live opens directly to its player and channel guide; promotional text is removed. Android Remote keeps its full control set in a quieter, more compact layout. The download page is a compact app directory (see download-simplicity-report.md).

## Changed source

- `live/index.html`, `live/styles.css`: simplified player, guide, search, installation dialog and footer. Accessible labels, recovery actions and attribution links remain.
- `live/app.mjs`: show the signal label for actual playback/offline/error states; remove the redundant native-player instruction. Playback, favorites, storage and bridge contracts are unchanged.
- `live/manifest.webmanifest`, `live/sw.js`: shared theme color and cache version 2 so installed copies refresh the new shell.
- `android/remote/src/main/java/com/in3rt1a/pctv/remote/MainActivity.java`: shared colors, compact controls, sentence-case labels; remove decorative branding and taglines. TV commands, discovery, pairing, persistence and control descriptions are unchanged.
- `android/remote/src/main/res/values/styles.xml`: matching accent and system chrome.
- `android/live/src/main/java/com/in3rt1a/pctv/live/MainActivity.java`: matching WebView background.
- `tests/live-browser.mjs`: install-dialog heading expectation follows the shortened visible title.
- `index.html`, `download.css`: download directory, independently checked and described in the download report.

## Verification

- Live catalogue: 4 tests passed with `node --test tests/live-catalog.test.mjs`.
- Live browser integration: passed native bridge, search, category filters, favorites persistence, install dialog, offline cached shell, excluded video caching, stream-error retry, and no uncaught browser errors.
- Web DOM checks: no horizontal overflow at 320, 390, 768 and 1280 pixels. Channels start at y332 and y371 on the two phone sizes. Ten channels remain available.
- Screenshots reviewed: `live-mobile.png` (390 by 844), `live-desktop_small.png` (900 by 593). Aligned controls and readable type; no clipped controls or text in the checked viewports.
- Remote Python: 20 tests passed with `py -3.11 -m unittest discover -s tests -p "remote_*.py" -v`.
- Native media URL boundary: Java test passed, rejecting 13 unsafe URLs and accepting one valid HTTPS URL.
- Android Remote debug build and both release lint tasks succeeded with JDK 21, one Gradle worker and a 512 MB heap. Live lint has 0 errors / 5 warnings; Remote lint has 0 errors / 13 warnings. Warnings cover existing Java string literals, RTL gravity, backup settings and WebView JavaScript.
- `git diff --check` passed (Git reports only expected LF/CRLF conversion notices).

## Build artifacts and integration

- Live: `android/live/build/outputs/apk/debug/live-debug.apk`.
- Remote: `android/remote/build/outputs/apk/debug/remote-debug.apk`.
- Successful main build/lint log: `docs/mobile-build-retry.log`.
- Final Live refresh log: `docs/mobile-live-build-final.log`.
- Integrate the changed source paths above into the original checkout, including the new download stylesheet. APKs are debug builds for review, not published releases. No commits, deployments, external uploads or personal-device installs were made.

## Limits

The first combined build hit host memory exhaustion in pip and the JVM; the reduced-memory retry succeeded. No emulator was launched because the machine was also running other review work. Native layouts were compiled and linted but not visually checked on an Android device in this pass. No physical TV command was sent. This pass did not rerun external live-stream availability tests; stream-error behavior and existing playback routing were exercised locally.

Final Live debug refresh succeeded (16 seconds, 3 tasks executed and 30 up-to-date). Download checks passed at four widths with setup open/closed: all 24 original destinations preserved; local screenshot copies are docs/download-desktop.png and docs/download-mobile.png.
