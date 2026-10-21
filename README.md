# PC TV Apps for Windows

Free beta downloads for **PC TV Remote / PC Cast** and **Beam**.

## Download

Open [the public beta release](https://github.com/clark719664/pc-tv-apps/releases/tag/v2026.10.20-beta.1) for setup notes, or download an app ZIP:

- **PC TV Remote / PC Cast:** [RokuRemote-public-external-tools.zip](https://github.com/clark719664/pc-tv-apps/releases/download/v2026.10.20-beta.1/RokuRemote-public-external-tools.zip)
- **Beam:** [Beam-1.1.0-public-external-tools.zip](https://github.com/clark719664/pc-tv-apps/releases/download/v2026.10.20-beta.1/Beam-1.1.0-public-external-tools.zip)

Compare downloads against [SHA256SUMS.txt](https://github.com/clark719664/pc-tv-apps/releases/download/v2026.10.20-beta.1/SHA256SUMS.txt).

Use the attached app ZIPs. GitHub's automatically generated source archives are not the Windows apps.

## PC TV Remote / PC Cast

A Windows app for TV remote control and PC casting. Roku discovery and device queries were verified with three Roku devices. Physical TV playback has not been tested. Samsung, LG, Vizio and Google TV functionality remains beta and has not been tested on physical hardware.

1. Extract the entire ZIP to a short location such as `%USERPROFILE%\PC-TV-Remote`. Long extraction paths can prevent the bundled browser from starting.
2. Open the extracted app folder and run `RokuRemote.exe`. Keep its accompanying files and folders together.
3. Keep the PC and TV on the same local network. For Roku PC Cast, follow the app's one-time developer-mode/channel setup and choose your own Roku developer password.

Direct playback of a compatible MP4 can work without FFmpeg. Conversion and web casting require FFmpeg installed separately.

## Beam

A Windows beta for finding web video and casting from your PC.

1. Extract the entire ZIP to a short location such as `%USERPROFILE%\Beam`.
2. Open the extracted `Beam` folder and run `Beam.exe`. Keep the accompanying files and read `README.txt`.
3. Keep the PC awake and on the same local network as the receiving device. Roku casting uses the one-time PC Cast developer-mode/channel setup.

Bridged playback requires FFmpeg installed separately. Chromecast, DLNA, older openAirPlay and browser-receiver paths remain beta. Physical playback has not been verified. Compatibility with every device, website or protected streaming service is not guaranteed.

## External tools and beta limits

FFmpeg, ffprobe and ADB are not bundled with these app ZIPs. Features that need those tools require a separate installation. The release notes include file sizes and SHA-256 checksums.

Automated checks and desktop smoke checks were completed before this public beta. Those checks do not establish physical playback compatibility.

## Free apps and optional creator support

The apps remain free forever. Optional creator support starts at $5 and provides the same app; it does not unlock extra features or include a support or update promise.
