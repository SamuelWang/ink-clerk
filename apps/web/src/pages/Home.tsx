import { Link } from 'react-router-dom'
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
        InkClerk is built around a single contract: AI edits land as drafts, you review the diff,
        and only your explicit accept turns a draft into the formal version of your document. No
        AI edit is ever applied silently.
      </p>
      <p>
        One way to start a draft is by importing an existing Google Doc. That import asks for
        read-only access to your Google Docs and Drive — just enough to fetch the document you
        choose, nothing else. See the <Link to="/privacy">Privacy Policy</Link> for exactly
        what's requested and how it's handled.
      </p>
      <div className="features">
        <h2>What InkClerk does</h2>
        <p>
          Available now: import a Google Doc, get AI help editing it through Claude, and review
          every AI change as a draft before it's accepted into your document.
        </p>
        <p>
          Planned: a desktop app with a full document editor and project/file management, a web
          app with the same features, and sync between desktop and web.
        </p>
      </div>
    </section>
  )
}
