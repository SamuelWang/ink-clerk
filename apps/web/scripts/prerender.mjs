import { build } from 'vite'
import { readFile, writeFile, mkdir, rm } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const distDir = path.join(root, 'dist')
const ssrOutDir = path.join(root, 'dist-ssr')

await build({
  root,
  logLevel: 'warn',
  build: {
    ssr: path.join(root, 'src/entry-server.tsx'),
    outDir: 'dist-ssr',
    emptyOutDir: true,
  },
})

const { renderRoute } = await import(pathToFileURL(path.join(ssrOutDir, 'entry-server.js')))

const template = await readFile(path.join(distDir, 'index.html'), 'utf-8')

const routes = [
  { pathname: '/', outFile: path.join(distDir, 'index.html'), title: 'InkClerk' },
  {
    pathname: '/privacy',
    outFile: path.join(distDir, 'privacy', 'index.html'),
    title: 'Privacy Policy · InkClerk',
  },
  {
    pathname: '/terms',
    outFile: path.join(distDir, 'terms', 'index.html'),
    title: 'Terms of Service · InkClerk',
  },
]

for (const route of routes) {
  const markup = renderRoute(route.pathname)
  const html = template
    .replace('<div id="root"></div>', `<div id="root">${markup}</div>`)
    .replace(/<title>.*<\/title>/, `<title>${route.title}</title>`)
  await mkdir(path.dirname(route.outFile), { recursive: true })
  await writeFile(route.outFile, html, 'utf-8')
  // Also write a flat `<name>.html` sibling alongside the `<name>/index.html` directory
  // form, since static hosts vary in which clean-URL resolution they use for a bare
  // `/privacy` request (no trailing slash) — this covers both conventions.
  if (route.outFile !== path.join(distDir, 'index.html')) {
    const flatFile = `${path.dirname(route.outFile)}.html`
    await writeFile(flatFile, html, 'utf-8')
  }
}

await rm(ssrOutDir, { recursive: true, force: true })
