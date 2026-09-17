const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '..');
const BASE = 'http://127.0.0.1:8767';
const TITLE = 'Gepetto’s Hoard';
let window;
// Keep the application identifier ASCII: Electron also uses it in User-Agent.
app.setName("Gepetto's Hoard");
app.setAppUserModelId('com.gepettos.hoard');

async function healthy() {
  let response;
  try {
    response = await fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(1500) });
  } catch {
    return false;
  }
  const value = await response.json().catch(() => ({}));
  if (response.ok && value.ok && value.application === 'sculptors-hoard') return true;
  throw Error(
    'Otra aplicación ocupa el puerto 8767. Ciérrala o cambia su puerto antes de abrir Sculptor’s Hoard.',
  );
}

async function ensureServer() {
  if (await healthy()) return;
  if (!fs.existsSync(path.join(ROOT, 'dist', 'index.html')))
    throw Error('Falta compilar la interfaz. Ejecuta npm run build.');
  const python =
    process.env.SCULPTORS_HOARD_PYTHON ||
    [
      path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
      path.join(ROOT, '.venv', 'bin', 'python'),
    ].find(fs.existsSync) ||
    (process.platform === 'win32' ? 'python' : 'python3');
  fs.mkdirSync(path.join(ROOT, 'logs'), { recursive: true });
  const log = fs.openSync(path.join(ROOT, 'logs', 'desktop-server.log'), 'a');
  const child = spawn(
    python,
    ['-X', 'utf8', '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '8767'],
    {
      cwd: ROOT,
      windowsHide: true,
      detached: true,
      stdio: ['ignore', log, log],
    },
  );
  let failure;
  child.on('error', (error) => {
    failure = error;
  });
  child.unref();
  fs.closeSync(log);
  for (let attempt = 0; attempt < 60; attempt++) {
    if (failure) throw Error(`No se pudo iniciar Python: ${failure.message}`);
    if (await healthy()) return;
    if (child.exitCode !== null) break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw Error(
    'No se pudo iniciar el servidor. Consulta logs/desktop-server.log y comprueba la instalación de Python.',
  );
}

async function openWindow() {
  await ensureServer();
  window = new BrowserWindow({
    width: 1440,
    height: 1000,
    minWidth: 900,
    minHeight: 640,
    title: TITLE,
    icon: path.join(ROOT, 'public', 'app-icon.png'),
    backgroundColor: '#fafbf6',
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.on('page-title-updated', (event) => {
    event.preventDefault();
    window.setTitle(TITLE);
  });
  window.once('ready-to-show', () => window.show());
  window.on('closed', () => {
    window = null;
  });
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url) && new URL(url).origin !== BASE) void shell.openExternal(url);
    return { action: 'deny' };
  });
  window.webContents.on('will-navigate', (event, url) => {
    if (new URL(url).origin !== BASE) event.preventDefault();
  });
  const project = process.argv.find((value) => value.startsWith('--project='))?.slice(10);
  await window.loadURL(
    BASE + (project && /^[a-f0-9]{12}$/.test(project) ? `/?project=${project}` : '/'),
  );
}

ipcMain.handle('pick-blender-project', async (event) => {
  if (
    !window ||
    event.sender !== window.webContents ||
    new URL(event.senderFrame.url).origin !== BASE
  )
    throw Error('Solicitud no válida.');
  const result = await dialog.showOpenDialog(window, {
    title: 'Abrir proyecto Blender',
    properties: ['openFile'],
    filters: [{ name: 'Proyecto Blender', extensions: ['blend'] }],
  });
  return result.canceled ? null : result.filePaths[0];
});

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', (_event, argv) => {
    if (!window) return;
    if (window.isMinimized()) window.restore();
    window.show();
    window.focus();
    const project = argv.find((value) => value.startsWith('--project='))?.slice(10);
    if (project && /^[a-f0-9]{12}$/.test(project))
      void window.loadURL(`${BASE}/?project=${project}`);
  });
  app
    .whenReady()
    .then(openWindow)
    .catch((error) => {
      dialog.showErrorBox(TITLE, error.message);
      app.quit();
    });
  app.on('window-all-closed', () => app.quit());
}
