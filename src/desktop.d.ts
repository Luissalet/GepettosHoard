export {};
declare global {
  interface Window {
    sculptorsHoardDesktop?: { pickBlend: () => Promise<string | null> };
  }
}
