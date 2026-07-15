import logo from '../assets/logo.png'

export default function Home() {
  return (
    <section className="page">
      <img src={logo} alt="InkClerk logo" width={120} height={120} className="hero-logo" />
      <h1>InkClerk</h1>
      <p className="lede">
        InkClerk is an AI-first clerical work platform built around a single contract: AI edits
        land as drafts, you review the diff, and only your explicit accept turns a draft into the
        formal version of your document. No AI edit is ever applied silently.
      </p>
      <div className="install">
        <h2>Install the Claude Code plugin</h2>
        {/*
          This marketplace listing resolves once the inkclerk plugin is submitted and approved
          (execution plan Task 12). Published here ahead of that so the OAuth verification
          reviewer sees the real install path this app links to.
        */}
        <pre>
          <code>
            /plugin marketplace add anthropics/claude-plugins-community{'\n'}
            /plugin install inkclerk@claude-community
          </code>
        </pre>
      </div>
    </section>
  )
}
