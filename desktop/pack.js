'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const platform = 'darwin';
const iconName = platform === 'win32' ? 'icon.ico' : 'icon.icns';
const hasIcon = fs.existsSync(path.join(__dirname, 'build', iconName));

if (!hasIcon) {
  console.warn('No app icon in desktop/build/; using the default. See desktop/build/README.md');
}

const args = [
  '.',
  'Geeked-Out Basketball',
  `--platform=${platform}`,
  '--out=out',
  '--overwrite',
  '--prune',
  '--productName=Geeked-Out Basketball',
];
if (hasIcon) {
  args.push('--icon=build/icon');
}

const result = spawnSync('electron-packager', args, {
  stdio: 'inherit',
  cwd: __dirname,
  env: process.env,
  shell: process.platform === 'win32',
});
process.exit(result.status === null ? 1 : result.status);
