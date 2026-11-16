/**
 * FOXFall preload bridge (restricted, modeled on Aster).
 * Exposes only: allowlisted invoke() and a single subscribable event channel.
 */
'use strict';
const { contextBridge, ipcRenderer } = require('electron');

let listeners = 0;
contextBridge.exposeInMainWorld('foxfall', {
  invoke: (action, payload = {}) => {
    if (typeof action !== 'string') {
      return Promise.resolve({ ok: false, error: 'invalid action' });
    }
    return ipcRenderer.invoke('foxfall:command', action, payload);
  },
  onEvent: (fn) => {
    if (listeners > 0) return () => undefined; // prevent duplicate listeners
    const handler = (_e, event) => {
      try {
        if (event && typeof event === 'object' && typeof event.event === 'string') {
          fn(event);
        }
      } catch (_) { /* renderer handler error must not break IPC */ }
    };
    ipcRenderer.on('foxfall:event', handler);
    listeners += 1;
    return () => {
      ipcRenderer.removeListener('foxfall:event', handler);
      listeners -= 1;
    };
  },
  backendStatus: () => ipcRenderer.invoke('foxfall:backend_status'),
});
