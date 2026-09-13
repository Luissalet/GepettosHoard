const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('sculptorsHoardDesktop', {
  pickBlend: () => ipcRenderer.invoke('pick-blender-project'),
});
