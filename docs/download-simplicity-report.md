# Download page simplicity pass

Changed `index.html` and added `download.css`.

- Replaced the marketing hero, repeated helper copy and screenshot gallery with four app rows and clear platform downloads.
- Moved installation instructions, compatibility limits and beta notes into a keyboard-accessible setup disclosure.
- Preserved all 24 distinct original anchor destinations, Payhip donation access, donor-message note and the complete third-party legal notice.
- Removed remote font requests; used system type, the shared neutral palette and blue primary actions.

Verification (2026-11-02):

- Headless Chrome/Playwright: PASS at widths 320, 390, 768 and 1280, with setup both open and closed (8 states). No horizontal overflow or measured clipped labels.
- Setup disclosure opens and closes with Enter. Four app entries render. No page JavaScript errors.
- Compared parsed anchor destinations against Git HEAD: 24/24 preserved.
- Visual review of desktop (900px preview) and phone (390px) screenshots: readable hierarchy, consistent alignment, no visible clipped controls.
- Local qwen3.5 extraction completed. Its later diff review did not complete before the model was unloaded for Android packaging; no further model calls were made.

Evidence outside the repository:

- `C:/Users/lil_c/AppData/Local/Temp/pc-cast-download-check.mjs`
- `C:/Users/lil_c/AppData/Local/Temp/pc-cast-download-check.json`
- `C:/Users/lil_c/AppData/Local/Temp/pc-cast-download-desktop_small.png`
- `C:/Users/lil_c/AppData/Local/Temp/pc-cast-download-mobile_small.png`

Limitations: checked local files in Chrome; no deployment, external download requests, or package installation was performed. Existing app download versions were preserved. No commits made.

Copied review evidence into this worktree: docs/download-check.json, docs/download-desktop.png (900px), docs/download-mobile.png (390px).
