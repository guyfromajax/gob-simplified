'use strict';

const { contextBridge } = require('electron');

const profile = process.env.GOB_BUILD_PROFILE || 'desktop';
const port = Number(process.env.GOB_LOOPBACK_PORT || 8765);

// Must land on window BEFORE franchiseContext.js / authGuard.js parse.
// contextBridge writes these into the isolated renderer world at document start.
contextBridge.exposeInMainWorld('GOB_BUILD_PROFILE', profile);
contextBridge.exposeInMainWorld('GOB_LOOPBACK_PORT', port);
contextBridge.exposeInMainWorld('gobDesktop', {
  profile: profile,
  loopbackPort: port,
});
