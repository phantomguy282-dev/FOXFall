/**
 * after-pack hook: embed the FOXFall icon and version info into the exe.
 * Uses rcedit directly because the build environment cannot extract the
 * electron-builder winCodeSign archive (NTFS symlink privilege).
 */
'use strict';
const path = require('path');

module.exports = async function afterPack(context) {
  const { rcedit } = require('rcedit');
  const exePath = path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.exe`);
  console.log(`after-pack: embedding icon into ${exePath}`);
  await rcedit(exePath, {
    icon: path.resolve(__dirname, '..', 'build', 'foxfall.ico'),
    'version-string': {
      ProductName: 'FOXFall',
      FileDescription: 'FOXFall — Your videos. Your world.',
      CompanyName: 'FOXFall Project',
    },
    'file-version': context.packager.appInfo.version,
    'product-version': context.packager.appInfo.version,
  });
  console.log('after-pack: icon + version info embedded');
};