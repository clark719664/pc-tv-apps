# Mobile third-party notices

PC TV Live uses the platform Android WebView and media player. Its bundled web app includes hls.js 1.7.3 and the BSD-2-Clause notice in `live/vendor/hls-LICENSE.txt`.

PC TV Remote bundles Chaquopy 17.1.0 (MIT), CPython 3.11.17 (PSF license), websocket-client 1.9.0 (Apache-2.0), androidtvremote2 0.3.1 (Apache-2.0), aiofiles 25.1.0 (Apache-2.0), cryptography 42.0.8 (Apache-2.0/BSD), cffi 1.17.1 (MIT), pycparser 3.12 (BSD), protobuf 7.36.2 (BSD), and libffi 3.3 (MIT). License texts retained from installed distributions are in this directory and bundled with the Remote APK. Python's platform dependencies are supplied by Chaquopy's Android runtime; its source recipes are at https://github.com/chaquo/chaquopy/tree/master/target.

Application code is separate from these third-party components. No FFmpeg, desktop Chromium, personal media, desktop configuration, owner pairing data, signing keys, or subscription credentials are included in the mobile packages.
