/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_CLIENT_ID: string
  readonly VITE_GOOGLE_PICKER_API_KEY: string
  readonly VITE_WEB_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
