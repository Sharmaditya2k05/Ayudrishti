/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the AyuDrishti app the landing page hands off to. */
  readonly VITE_APP_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
