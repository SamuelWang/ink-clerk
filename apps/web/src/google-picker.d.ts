export {}

interface GoogleTokenResponse {
  access_token?: string
  expires_in?: number
  error?: string
}

interface GoogleTokenClient {
  requestAccessToken(): void
}

interface GoogleDocsView {
  setMimeTypes(mimeTypes: string): GoogleDocsView
}

interface GooglePickerResponse {
  action: string
  docs: Array<{ id: string; name: string }>
}

interface GooglePicker {
  setVisible(visible: boolean): void
}

interface GooglePickerBuilder {
  addView(view: GoogleDocsView): GooglePickerBuilder
  setOAuthToken(token: string): GooglePickerBuilder
  setDeveloperKey(key: string): GooglePickerBuilder
  setCallback(callback: (data: GooglePickerResponse) => void): GooglePickerBuilder
  build(): GooglePicker
}

declare global {
  interface Window {
    google: {
      accounts: {
        oauth2: {
          initTokenClient(config: {
            client_id: string
            scope: string
            callback: (response: GoogleTokenResponse) => void
          }): GoogleTokenClient
        }
      }
      picker: {
        PickerBuilder: new () => GooglePickerBuilder
        DocsView: new (viewId?: unknown) => GoogleDocsView
        ViewId: { DOCS: unknown }
        Action: { PICKED: string }
      }
    }
    gapi: {
      load(api: string, callback: () => void): void
    }
  }
}
