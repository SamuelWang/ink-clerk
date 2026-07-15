export default function Privacy() {
  return (
    <article className="page legal">
      <h1>Privacy Policy</h1>
      <p className="effective-date">Effective date: July 14, 2026</p>

      <p>
        This page describes exactly what the InkClerk Google Docs import feature collects, where
        it goes, and how long it lives. InkClerk's Google OAuth broker (a small hosted service,
        <code>apps/web-api</code>) exists for one purpose: to let you import a Google Doc without
        needing to set up your own Google Cloud OAuth client.
      </p>

      <h2>What we request from Google</h2>
      <p>
        The broker requests exactly two read-only OAuth scopes:{' '}
        <code>documents.readonly</code> and <code>drive.readonly</code>. It never requests your
        name, email, profile picture, or any write access to your Google account.
      </p>

      <h2>How the flow works</h2>
      <p>
        When you run the InkClerk plugin's Google Docs import, it opens your browser to our
        broker, you sign in and consent directly with Google, and Google redirects back to the
        broker with a one-time authorization code.
      </p>

      <h2>What the broker stores, and for how long</h2>
      <p>
        The broker holds the resulting access and refresh tokens in an in-memory session store
        only &mdash; a plain, in-process data structure, not a database. Each entry is keyed by a
        random session id and is deleted the first time it is read (single-claim): a repeat or
        late request for the same session id afterward sees "expired," not your tokens again. If
        never claimed, the entry is dropped automatically after five minutes. Nothing is ever
        written to disk on the broker, so restarting the service erases all of this state
        instantly.
      </p>
      <p>
        The token-refresh endpoint is stateless: it does not touch the session store at all. It
        simply forwards your refresh token to Google's own token endpoint and returns the result.
      </p>

      <h2>Where your tokens actually live long-term</h2>
      <p>
        Your access token, refresh token, and expiry are cached only on your own machine, at{' '}
        <code>~/.config/inkclerk/google-token.json</code>. InkClerk's servers never persist these
        long-term &mdash; once a session is claimed, the broker has nothing left to store.
      </p>

      <h2>What we don't collect</h2>
      <p>
        No other personal data is collected, stored, sold, or shared. This site uses no analytics
        or tracking scripts.
      </p>

      <h2>Third parties</h2>
      <p>
        Google's own{' '}
        <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">
          privacy policy
        </a>{' '}
        governs your Google account and the data Google's APIs return to you directly.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about this policy: <a href="mailto:chieh0919@gmail.com">chieh0919@gmail.com</a>.
      </p>
    </article>
  )
}
