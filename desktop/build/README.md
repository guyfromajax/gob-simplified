# Desktop app icon

`npm run pack` keeps `productName` "Geeked-Out Basketball". It passes `--icon=build/icon` only when `icon.icns` (mac) or `icon.ico` (win) is in this folder. Otherwise it uses Electron's default icon and prints a one-line warning.

No ≥512px **square** brand mark exists in the repo (see the task report). Do not invent one.

Jamie needs to drop these files here, generated from a square brand source ≥512px:

| File | Platform |
|---|---|
| `icon.icns` | macOS (1024, 512, 256, 128, 64, 32, 16) |
| `icon.ico` | Windows (256, 48, 32, 16) |
| `icon.png` | 512×512 (and optionally 1024×1024) PNG |
