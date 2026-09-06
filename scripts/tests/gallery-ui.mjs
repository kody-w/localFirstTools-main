import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { chromium } from "playwright"

const args = process.argv.slice(2)
const option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback
const base = option("--url", "http://127.0.0.1:8768")
const components = option("--components", "http://127.0.0.1:5174/components.html")
const output = option("--screenshots", "")
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")
const executable = process.env.CHROME_BIN || (process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : undefined)
const browser = await chromium.launch({ executablePath: executable, headless: true, chromiumSandbox: true })
let checks = 0
const contexts = []

async function context(options = {}) {
  const value = await browser.newContext({ reducedMotion: "reduce", ...options })
  contexts.push(value)
  return value
}

async function loaded(page, url) {
  await page.goto(url, { waitUntil: "networkidle" })
  await page.locator("#glass-gallery-root h1").waitFor()
  await page.locator("#feed .post").first().waitFor()
  await page.getByRole("button", { name: "Browse as guest", exact: true }).click()
}

function noOverflow(geometry, width) {
  assert(geometry.scrollWidth <= width && geometry.viewport === width, JSON.stringify(geometry))
}

async function mobileNavigation(page) {
  const toggle = page.getByRole("button", { name: "Toggle sidebar", exact: true })
  const sidebar = page.locator("#sidebar")
  for (const target of [toggle, page.locator("#player-chip"), page.locator("#feed .vote-btn").first()]) {
    const box = await target.boundingBox()
    assert(box && box.width >= 44 && box.height >= 44, `Touch target must be at least 44px: ${JSON.stringify(box)}`)
  }
  for (const reducedMotion of ["reduce", "no-preference"]) {
    await page.emulateMedia({ reducedMotion })
    assert.equal(await sidebar.isVisible(), false)
    assert.equal(await toggle.getAttribute("aria-expanded"), "false")
    await toggle.focus()
    await page.keyboard.press("Enter")
    await sidebar.waitFor({ state: "visible" })
    assert.equal(await toggle.getAttribute("aria-expanded"), "true")
    assert.equal(await sidebar.getByRole("link", { name: "Podcast", exact: true }).getAttribute("href"), "apps/broadcasts/player.html")
    await sidebar.getByRole("button", { name: "Dimensions", exact: true }).click()
    await page.locator("#dim-overlay").waitFor({ state: "visible" })
    await page.getByRole("button", { name: "Close dimensions", exact: true }).click()
    await sidebar.locator('[data-c="all"]').click()
    assert.equal(await sidebar.isVisible(), false)
    assert.equal(await toggle.getAttribute("aria-expanded"), "false")
    assert.equal(await toggle.evaluate(element => element === document.activeElement), true)
  }
  await page.emulateMedia({ reducedMotion: "reduce" })
}

async function agentOnboarding(page, theme, width) {
  const trigger = page.getByRole("button", { name: "Bring your agent", exact: true })
  const dialog = page.getByRole("dialog", { name: "Send Your Agent to the Zoo", exact: true })
  const close = page.getByRole("button", { name: "Close agent onboarding", exact: true })
  await trigger.focus()
  await page.keyboard.press("Enter")
  await dialog.waitFor()
  assert.equal(await close.evaluate(element => element === document.activeElement), true)
  const box = await close.boundingBox()
  assert(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= width && box.height >= 44)
  assert.equal(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth), true)
  await page.keyboard.press("Shift+Tab")
  assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true)
  await page.keyboard.press("Tab")
  assert.equal(await close.evaluate(element => element === document.activeElement), true)
  await dialog.getByRole("button", { name: "Agent API", exact: false }).click()
  await page.locator("#panel-api").waitFor()
  await dialog.getByRole("button", { name: "Skill File", exact: false }).click()
  if (output) await page.screenshot({ path: path.join(output, `agent-${theme}-${width}.png`) })
  await close.click()
  assert.equal(await dialog.isVisible(), false)
  assert.equal(await trigger.evaluate(element => element === document.activeElement), true)
  await page.keyboard.press("Enter")
  await dialog.waitFor()
  await page.keyboard.press("Escape")
  assert.equal(await dialog.isVisible(), false)
  assert.equal(await trigger.evaluate(element => element === document.activeElement), true)
}

try {
  if (output) await fs.mkdir(output, { recursive: true })
  for (const theme of ["light", "dark"]) {
    for (const width of [1440, 390, 320]) {
      const ctx = await context({ viewport: { width, height: 1000 }, colorScheme: theme })
      const page = await ctx.newPage()
      const errors = []
      page.on("pageerror", error => errors.push(error.message))
      await loaded(page, `${base}/?scoutTheme=${theme}`)
      const geometry = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth, viewport: innerWidth,
        theme: document.documentElement.dataset.theme,
        background: getComputedStyle(document.body).backgroundColor,
        font: getComputedStyle(document.body).fontFamily,
      }))
      noOverflow(geometry, width)
      assert.equal(geometry.theme, theme)
      assert(geometry.font.includes("Segoe UI"))
      assert.equal(geometry.background, theme === "light" ? "rgb(247, 244, 239)" : "rgb(61, 59, 58)")
      const action = await page.getByRole("button", { name: "Explore the collection", exact: true }).boundingBox()
      assert(action && action.height >= 44 && action.x >= 0 && action.x + action.width <= width)
      if (width < 800) await mobileNavigation(page)
      await page.evaluate(() => scrollTo(0, 0))
      assert.deepEqual(errors, [])
      if (output) await page.screenshot({ path: path.join(output, `gallery-${theme}-${width}.png`) })
      if (width === 320 || width === 1440) {
        await agentOnboarding(page, theme, width)
        checks++
      }
      assert.deepEqual(errors, [])
      checks++
      await ctx.close()
    }
  }

  const ctx = await context({ viewport: { width: 1440, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  page.on("pageerror", error => errors.push(error.message))
  await loaded(page, `${base}/?scoutTheme=light`)
  const total = await page.locator("#feed .post").count()
  const firstTitle = (await page.locator(".post-title").first().textContent()).trim()
  await page.getByRole("button", { name: "Explore the collection", exact: true }).click()
  assert.equal(await page.locator("#q").evaluate(element => element === document.activeElement), true)
  await page.locator("#q").fill(firstTitle)
  await page.waitForFunction(expected => document.querySelectorAll("#feed .post").length < expected, total)
  assert((await page.locator("#feed").textContent()).includes(firstTitle))
  await page.locator("#q").fill("__glass_no_matching_app__")
  await page.locator("#empty").waitFor()
  assert.equal(await page.locator("#feed .post").count(), 0)
  await page.locator("#q").fill("")
  await page.waitForFunction(expected => document.querySelectorAll("#feed .post").length === expected, total)
  checks++

  await page.getByRole("button", { name: "Featured finds", exact: true }).click()
  assert(await page.locator('.sub-link[data-c="featured"]').evaluate(element => element.classList.contains("active")))
  assert((await page.locator("#feed .post").count()) > 0)
  await page.locator('.sub-link[data-c="all"]').click()
  await page.locator('.sort-tab[data-s="name"]').click()
  assert(await page.locator('.sort-tab[data-s="name"]').evaluate(element => element.classList.contains("active")))
  checks++

  await page.getByRole("button", { name: "List view", exact: true }).click()
  assert.equal(await page.locator("html").getAttribute("data-gallery-view"), "list")
  await page.reload({ waitUntil: "networkidle" })
  await page.locator("#glass-gallery-root h1").waitFor()
  await page.getByRole("button", { name: "Browse as guest", exact: true }).click()
  assert.equal(await page.locator("html").getAttribute("data-gallery-view"), "list")
  await page.getByRole("button", { name: "Grid view", exact: true }).click()
  await page.getByRole("button", { name: "Use dark theme", exact: true }).click()
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark")
  await page.goto(base, { waitUntil: "networkidle" })
  await page.locator("#glass-gallery-root h1").waitFor()
  await page.getByRole("button", { name: "Browse as guest", exact: true }).click()
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark")
  checks++

  await page.locator(".post-title").first().click()
  await page.getByRole("dialog", { name: "Application details" }).waitFor()
  await page.getByRole("button", { name: "Close application details" }).click()
  await page.mouse.move(0, 0)
  assert.equal(await page.locator("#modal-bg").isVisible(), false)
  await page.locator("body").click({ position: { x: 290, y: 85 } })
  await page.keyboard.press("/")
  assert.equal(await page.locator("#q").evaluate(element => element === document.activeElement), true)
  checks++

  const demo = await ctx.newPage()
  const demoErrors = []
  demo.on("pageerror", error => demoErrors.push(error.message))
  await demo.goto(components, { waitUntil: "networkidle" })
  await demo.getByRole("button", { name: "Liquid action", exact: true }).waitFor()
  await demo.getByRole("button", { name: "Liquid action", exact: true }).click()
  assert.equal(await demo.locator("[data-clicks]").textContent(), "1")
  await demo.getByRole("link", { name: "Slotted link", exact: false }).click()
  assert.equal(await demo.locator("[data-clicks]").textContent(), "2")
  assert(new URL(demo.url()).hash === "#destination")
  const ids = await demo.locator("filter").evaluateAll(nodes => nodes.map(node => node.id))
  assert.equal(new Set(ids).size, ids.length)
  assert(ids.length >= 4)
  await demo.getByRole("button", { name: "Focus forwarded ref", exact: true }).click()
  assert.equal(await demo.getByRole("button", { name: "Liquid action", exact: true }).evaluate(element => element === document.activeElement), true)
  checks++

  const disabled = demo.getByRole("link", { name: "Disabled link", exact: true })
  await disabled.focus()
  await demo.keyboard.press("Enter")
  assert.equal(await demo.locator("[data-clicks]").textContent(), "2")
  assert(new URL(demo.url()).hash !== "#blocked")
  const metal = demo.getByRole("button", { name: "Metal default", exact: true })
  await metal.click()
  assert.equal(await demo.locator("[data-clicks]").textContent(), "3")
  assert.equal(await demo.locator("[data-pointers]").textContent(), "1")
  await metal.focus()
  await demo.keyboard.down("Space")
  assert.equal(await metal.locator("..").getAttribute("data-pressed"), "true")
  await demo.keyboard.up("Space")
  assert.equal(await metal.locator("..").getAttribute("data-pressed"), "false")
  assert.equal(await demo.locator("[data-clicks]").textContent(), "4")
  await metal.hover()
  await demo.mouse.down()
  await demo.mouse.move(0, 0)
  await demo.mouse.up()
  assert.equal(await demo.locator("[data-clicks]").textContent(), "4", "Dragging off a button must cancel activation.")
  assert.equal(await metal.locator("..").getAttribute("data-pressed"), "false")
  assert.deepEqual(demoErrors, [])
  checks++

  const offline = await context({ offline: true, serviceWorkers: "block", viewport: { width: 1000, height: 900 } })
  await offline.route("**/*", async route => {
    const request = new URL(route.request().url())
    if (request.origin !== new URL(base).origin) { await route.abort(); return }
    const relative = decodeURIComponent(request.pathname === "/" ? "/index.html" : request.pathname)
    const file = path.resolve(repo, "." + relative)
    if (!file.startsWith(repo + path.sep)) { await route.abort(); return }
    try {
      const body = await fs.readFile(file)
      const type = file.endsWith(".json") ? "application/json" : file.endsWith(".html") ? "text/html" : "application/octet-stream"
      await route.fulfill({ status: 200, contentType: type, body })
    } catch (error) {
      if (error.code !== "ENOENT") throw error
      await route.fulfill({ status: 404, body: "Not found" })
    }
  })
  const offlinePage = await offline.newPage()
  const offlineErrors = []
  offlinePage.on("pageerror", error => offlineErrors.push(error.message))
  await loaded(offlinePage, `${base}/?scoutTheme=light`)
  await offlinePage.getByRole("button", { name: "Explore the collection", exact: true }).click()
  await offlinePage.locator("#q").fill(firstTitle)
  await offlinePage.waitForFunction(expected => document.querySelectorAll("#feed .post").length < expected, total)
  assert((await offlinePage.locator("#feed").textContent()).includes(firstTitle))
  assert.deepEqual(offlineErrors, [])
  assert.deepEqual(errors, [])
  checks++
  console.log(JSON.stringify({
    status: "passed", checks, apps: total,
    scope: "Actual built gallery; both themes; desktop and mobile; local repository data works with browser networking disabled.",
    offline_boundary: "Gallery JSON data is served from the local clone. The standalone HTML alone does not include every app or all platform data.",
  }))
} finally {
  for (const ctx of contexts) await ctx.close()
  await browser.close()
}
