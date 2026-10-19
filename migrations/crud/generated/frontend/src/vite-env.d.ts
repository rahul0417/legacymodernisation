/// <reference types="vite/client" />

// Augment the default ImportMetaEnv with our VITE_-prefixed vars.
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
