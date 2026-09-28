const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('sculptorsHoardDesktop', {
  pickBlend: () => ipcRenderer.invoke('pick-blender-project'),
  pickPortable: (folder = false) => ipcRenderer.invoke('pick-portable-project', folder),
  savePortable: () => ipcRenderer.invoke('save-portable-project'),
});
