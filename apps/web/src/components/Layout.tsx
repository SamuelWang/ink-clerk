import { Link, Outlet } from 'react-router-dom'
import logo from '../assets/logo.png'

export default function Layout() {
  return (
    <>
      <header className="site-header">
        <Link to="/" className="brand">
          <img src={logo} alt="InkClerk logo" width={40} height={40} />
          <span>InkClerk</span>
        </Link>
        <nav>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>
          &copy; {new Date().getFullYear()} InkClerk &middot;{' '}
          <a href="mailto:chieh0919@gmail.com">chieh0919@gmail.com</a> &middot;{' '}
          <a
            href="https://github.com/SamuelWang/ink-clerk/issues/new"
            target="_blank"
            rel="noreferrer"
          >
            Report an issue
          </a>
        </p>
      </footer>
    </>
  )
}
