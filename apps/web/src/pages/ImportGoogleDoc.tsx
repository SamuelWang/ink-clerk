import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const GIS_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'
const PICKER_SCRIPT_SRC = 'https://apis.google.com/js/api.js'
const DRIVE_FILE_SCOPE = 'https://www.googleapis.com/auth/drive.file'

function loadScriptOnce(src: string): Promise<void> {
  const script = document.createElement('script')
  script.src = src
  script.async = true
  const promise = new Promise<void>((resolve, reject) => {
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load ${src}`))
  })
  document.head.appendChild(script)
  return promise
}

let gisPromise: Promise<void> | null = null
function loadGis(): Promise<void> {
  gisPromise ??= loadScriptOnce(GIS_SCRIPT_SRC)
  return gisPromise
}

let pickerLibPromise: Promise<void> | null = null
function loadPickerLib(): Promise<void> {
  pickerLibPromise ??= loadScriptOnce(PICKER_SCRIPT_SRC).then(
    () => new Promise<void>((resolve) => window.gapi.load('picker', () => resolve())),
  )
  return pickerLibPromise
}

type Status = 'idle' | 'signing-in' | 'picking' | 'completing' | 'done' | 'error'

export default function ImportGoogleDoc() {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id')
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    loadGis().catch(() => setError('Could not load Google Sign-In. Check your connection and reload.'))
  }, [])

  async function openPicker(accessToken: string, expiresIn: number) {
    setStatus('picking')
    await loadPickerLib()

    const view = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS).setMimeTypes(
      'application/vnd.google-apps.document',
    )
    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(accessToken)
      .setDeveloperKey(import.meta.env.VITE_GOOGLE_PICKER_API_KEY)
      .setCallback((data) => {
        if (data.action !== window.google.picker.Action.PICKED) {
          return
        }
        const doc = data.docs[0]
        void completeSession(accessToken, expiresIn, doc.id, doc.name, doc.resourceKey ?? '')
      })
      .build()
    picker.setVisible(true)
  }

  async function completeSession(
    accessToken: string,
    expiresIn: number,
    fileId: string,
    fileName: string,
    resourceKey: string,
  ) {
    setStatus('completing')
    try {
      const response = await fetch(
        `${import.meta.env.VITE_WEB_API_URL}/import/google-doc/session/${sessionId}/complete`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            access_token: accessToken,
            expires_in: expiresIn,
            file_id: fileId,
            file_name: fileName,
            resource_key: resourceKey,
          }),
        },
      )
      if (!response.ok) {
        throw new Error('relay rejected the completion')
      }
      setStatus('done')
    } catch {
      setStatus('error')
      setError('Could not reach InkClerk to finish the import. You can close this tab and try again.')
    }
  }

  function handleSignIn() {
    if (!sessionId) {
      setStatus('error')
      setError('Missing session — open this page from the InkClerk import command, not directly.')
      return
    }
    setStatus('signing-in')
    setError('')

    const tokenClient = window.google.accounts.oauth2.initTokenClient({
      client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
      scope: DRIVE_FILE_SCOPE,
      prompt: 'select_account',
      callback: (response) => {
        if (response.error || !response.access_token) {
          setStatus('error')
          setError('Google sign-in failed or was cancelled.')
          return
        }
        void openPicker(response.access_token, response.expires_in ?? 3600)
      },
    })
    tokenClient.requestAccessToken()
  }

  return (
    <section className="page">
      <h1>Import a Google Doc</h1>
      {status === 'idle' && (
        <>
          <p>Sign in with Google, then choose the document you want to import into InkClerk.</p>
          <button type="button" onClick={handleSignIn}>
            Sign in with Google
          </button>
        </>
      )}
      {status === 'signing-in' && <p>Waiting for Google sign-in&hellip;</p>}
      {status === 'picking' && <p>Choose the document you want to import&hellip;</p>}
      {status === 'completing' && <p>Finishing up&hellip;</p>}
      {status === 'done' && <p>Done &mdash; you can return to your terminal.</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  )
}
