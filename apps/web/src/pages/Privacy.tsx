export default function Privacy() {
  return (
    <article className="page legal">
      <h1>Privacy Policy</h1>
      <p className="effective-date">Effective date: July 17, 2026</p>

      <p>
        This page describes exactly what InkClerk's Google Docs import feature collects, why, and
        how long it's kept.
      </p>

      <h2>What we access</h2>
      <p>
        When you import a Google Doc, you pick the specific document yourself through Google's
        own file picker. InkClerk only ever gets access to that one document &mdash; never
        general access to your Google Drive, and never your name, email, profile picture, or any
        write access to your Google account.
      </p>

      <h2>How long we keep it</h2>
      <p>
        Your Google access is cached only on your own machine. You sign in and pick the document
        directly with Google, in your browser &mdash; InkClerk's servers are never part of that
        exchange and never see your Google credentials. They only relay a momentary, one-time
        handoff of the document you picked from your browser back to your own machine, and don't
        keep a permanent copy of your Google access afterward.
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
