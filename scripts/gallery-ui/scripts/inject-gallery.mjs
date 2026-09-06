import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..")
const project = path.join(root, "scripts/gallery-ui")
const target = path.join(root, "index.html")
const [original, css, js] = await Promise.all([
  fs.readFile(target, "utf8"),
  fs.readFile(path.join(project, "dist/gallery-ui.css"), "utf8"),
  fs.readFile(path.join(project, "dist/gallery-ui.js"), "utf8"),
])

function replaceRegion(document, name, content) {
  const start = `<!-- ${name}:start -->`
  const end = `<!-- ${name}:end -->`
  const from = document.indexOf(start), to = document.indexOf(end)
  if (from < 0 || to < from || document.indexOf(start, from + 1) >= 0) {
    throw new Error(`Missing or ambiguous generated region: ${name}`)
  }
  return document.slice(0, from) + start + "\n" + content + "\n" + document.slice(to)
}

let result = replaceRegion(original, "glass-gallery-styles", `<style id="glass-gallery-styles">\n${css.replaceAll("</style", "<\\/style")}\n</style>`)
result = replaceRegion(result, "glass-gallery-script", `<script>\n${js.replaceAll("</script", "<\\/script")}\n</script>`)
if (/<(?:script|link)\b[^>]*(?:src|href)=["'][^"']+\.(?:js|css)["']/i.test(result)) {
  throw new Error("The delivered gallery must not require an external JavaScript or stylesheet file.")
}
const temporary = target + ".glass-build"
try {
  await fs.writeFile(temporary, result, { flag: "wx" })
  await fs.rename(temporary, target)
} finally {
  await fs.rm(temporary, { force: true })
}
console.log(`Updated index.html with ${Buffer.byteLength(js)} JS bytes and ${Buffer.byteLength(css)} CSS bytes.`)
