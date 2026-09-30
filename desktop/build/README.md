# Desktop app icon

electron-packager is wired to `--icon=build/icon` and `productName` "Geeked-Out Basketball".

No ≥512px **square** brand mark exists in the repo (see the task report). Do not invent one.

Jamie needs to drop these files here, generated from a square brand source ≥512px:

| File | Platform |
|---|---|
| `icon.icns` | macOS (1024, 512, 256, 128, 64, 32, 16) |
| `icon.ico` | Windows (256, 48, 32, 16) |
| `icon.png` | 512×512 (and optionally 1024×1024) PNG |

Until those files exist, `npm run pack` will fail on the missing icon. That is intentional.
