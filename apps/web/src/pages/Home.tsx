import logo from '../assets/logo.png'

export default function Home() {
  return (
    <section className="page">
      <img src={logo} alt="InkClerk logo" width={120} height={120} className="hero-logo" />
      <h1>InkClerk</h1>
      <p className="lede">
        InkClerk helps you edit documents with an AI assistant, without ever losing control of
        what changes: every AI edit is shown to you as a draft first, and nothing becomes part of
        your document until you review it and explicitly accept it.
      </p>
      <p>
        InkClerk is built around a single contract: AI edits land as drafts, you review the
        changes, and only your explicit accept turns a draft into the formal version of your
        document. No AI edit is ever applied silently.
      </p>
      <div className="features">
        <h2>What InkClerk does</h2>
        <p>
          Your documents are plain Markdown files, stored locally on your own disk and organized
          into projects, that you fully own — not a proprietary format locked into InkClerk.
          Available now, as an add-on inside
          Claude Code (Anthropic's AI coding assistant) — InkClerk isn't its own app yet, you use
          it there. You can import an existing Google Doc as a starting point (picked through
          Google's own file picker, so InkClerk only ever gets access to the one document you
          choose), ask for an edit to any document, and review each proposed change as a draft:
          accept it to make it official, or reject it to leave your document untouched.
        </p>
        <p>
          Planned: a desktop app with a full document editor and project/file management, a web
          app with the same features, and sync between desktop and web.
        </p>
      </div>
    </section>
  )
}
