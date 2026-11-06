import type { CapacitorConfig } from '@capacitor/cli';
// Defina FLASH_PUBLIC_URL como a URL HTTPS do site publicado antes de compilar.
const url = process.env.FLASH_PUBLIC_URL;
const config: CapacitorConfig = {
  appId: 'br.com.flash.servicos',
  appName: 'Flash',
  webDir: 'www',
  ...(url ? { server: { url, cleartext: false } } : {}),
};
export default config;
