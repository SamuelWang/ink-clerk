import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import AppRoutes from './AppRoutes'

export function renderRoute(pathname: string): string {
  return renderToStaticMarkup(
    <StaticRouter location={pathname}>
      <AppRoutes />
    </StaticRouter>,
  )
}
