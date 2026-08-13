/**
 * Assembles dist/ into a loadable unpacked Overwolf app.
 *
 * `tsc` emits the compiled modules; this copies the manifest, HTML and icons
 * alongside them, so `dist/` is exactly the folder to select in
 * "Load unpacked extension".
 */

import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, 'dist');

mkdirSync(dist, { recursive: true });

for (const name of ['background.html', 'debug.html']) {
  cpSync(join(root, 'public', name), join(dist, name));
}

if (existsSync(join(root, 'icons'))) {
  cpSync(join(root, 'icons'), join(dist, 'icons'), { recursive: true });
}

const manifest = JSON.parse(readFileSync(join(root, 'manifest.json'), 'utf8'));
writeFileSync(join(dist, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

const required = ['background.js', 'debug.js', 'background.html', 'debug.html', 'manifest.json'];
const missing = required.filter((name) => !existsSync(join(dist, name)));
if (missing.length > 0) {
  console.error(`build incomplete, missing: ${missing.join(', ')}`);
  process.exit(1);
}

console.log(`built unpacked app: ${dist}`);
console.log('Load this folder in Overwolf -> Settings -> About -> Development options.');
