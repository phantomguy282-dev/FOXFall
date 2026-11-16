/**
 * after-pack hook: embed the FOXFall icon and version info into the exe.
 * Uses rcedit directly because the build environment cannot extract the
 * electron-builder winCodeSign archive (NTFS symlink privilege).
 *
 * rcedit can fail transiently while antivirus/electron-builder still holds
 * the fresh exe open, so a few bounded retries are applied.
 */
'use strict';
const path = require('path');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function rceditWithRetry(rcedit, exePath, options, attempts = 5) {
  let lastError;
  for (let i = 1; i <= attempts; i++) {
    try {
      await rcedit(exePath, options);
      return;
    } catch (err) {
      lastError = err;
      console.warn(`after-pack: rcedit attempt ${i}/${attempts} failed: ${err.message}`);
      await sleep(1500 * i);
    }
  }
  throw lastError;
}

module.exports = async function afterPack(context) {
  const { rcedit } = require('rcedit');
  const exePath = path.join(
    context.appOutDir, `${context.packager.appInfo.productFilename}.exe`);
  console.log(`after-pack: embedding icon into ${exePath}`);
  await rceditWithRetry(rcedit, exePath, {
    icon: path.resolve(__dirname, '..', '..', 'assets', 'foxfall.ico'),
    'version-string': {
      ProductName: 'FOXFall',
      FileDescription: 'FOXFall - Your videos. Your world.',
      CompanyName: 'FOXFall Project',
    },
    'file-version': context.packager.appInfo.version,
    'product-version': context.packager.appInfo.version,
  });
  console.log('after-pack: icon + version info embedded');
};