import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { chromium } from "playwright"

const args = process.argv.slice(2)
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")
const file = path.resolve(option("--file", path.join(root, "apps/creative-tools/cyber-timer.html")))
const screenshot = option("--screenshot", "")
const source = await fs.readFile(file, "utf8")
const executablePath = process.env.CHROME_BIN || (process.platform === "darwin"
  ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  : undefined)
const browser = await chromium.launch({ executablePath, headless: true, chromiumSandbox: true })
let checks = 0

try {
  const context = await browser.newContext({ offline: true, serviceWorkers: "block", reducedMotion: "reduce", viewport: { width: 1280, height: 900 } })
  await context.route("**/*", route => route.request().url() === "https://timer.test/"
    ? route.fulfill({ status: 200, contentType: "text/html", body: source })
    : route.abort())
  const page = await context.newPage()
  const errors = []
  page.on("pageerror", error => errors.push(error.message))
  await page.clock.install({ time: new Date("2026-09-06T12:00:00Z") })
  await page.goto("https://timer.test/", { waitUntil: "load" })
  const display = page.locator("#timer")
  const start = page.getByRole("button", { name: "INITIATE", exact: true })
  const pause = page.getByRole("button", { name: "HALT", exact: true })
  const reset = page.getByRole("button", { name: "REBOOT", exact: true })
  const work = page.getByRole("button", { name: "WORK_CYCLE", exact: true })
  const rest = page.getByRole("button", { name: "COOLDOWN", exact: true })

  for (const viewport of [{ width: 320, height: 700 }, { width: 390, height: 844 }, { width: 844, height: 360 }]) {
    await page.setViewportSize(viewport)
    const container = await page.locator(".container").boundingBox()
    assert(container && container.x >= 0 && container.x + container.width <= viewport.width, `Timer must fit ${viewport.width}px: ${JSON.stringify(container)}`)
    for (const button of await page.getByRole("button").all()) {
      await button.scrollIntoViewIfNeeded()
      const box = await button.boundingBox()
      assert(box && box.x >= 0 && box.x + box.width <= viewport.width && box.y >= 0 && box.y + box.height <= viewport.height, `Control must be reachable: ${JSON.stringify(box)}`)
      assert(box.width >= 44 && box.height >= 44, "Timer controls must retain 44px touch targets.")
    }
    await page.evaluate(() => scrollTo(0, 0))
    if (screenshot && viewport.width === 320) {
      const parsed = path.parse(path.resolve(screenshot))
      await page.screenshot({ path: path.join(parsed.dir, parsed.name + "-mobile" + parsed.ext) })
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.evaluate(() => scrollTo(0, 0))
  checks++

  assert.equal(await display.textContent(), "25:00")
  await start.click()
  await page.clock.fastForward(61000)
  assert.equal(await display.textContent(), "23:59", "One delayed callback must account for 61 elapsed seconds.")
  assert.equal(await display.getAttribute("data-text"), "23:59")
  assert((await page.title()).includes("23:59"))
  checks++

  await pause.click()
  await page.clock.fastForward(60000)
  assert.equal(await display.textContent(), "23:59", "Paused time must not be consumed.")
  await start.click()
  await page.clock.fastForward(1500)
  assert.equal(await display.textContent(), "23:58")
  checks++

  await reset.click()
  await start.click()
  await page.clock.runFor(250)
  await pause.click()
  await page.clock.fastForward(10000)
  await start.click()
  await page.clock.runFor(750)
  assert.equal(await display.textContent(), "24:59", "Pause/resume must preserve fractional elapsed time.")
  checks++

  await rest.click()
  assert.equal(await display.textContent(), "05:00")
  await page.clock.fastForward(120000)
  assert.equal(await display.textContent(), "05:00", "Changing mode must stop the previous interval.")
  await start.click()
  await page.clock.fastForward(15 * 60 * 1000)
  assert.equal(await display.textContent(), "00:00")
  assert.equal(await page.locator("#status").textContent(), "SEQUENCE COMPLETE.")
  await page.clock.fastForward(5000)
  assert.equal(await display.textContent(), "00:00", "An overdue timer must stop at zero.")
  checks++

  await start.click()
  assert.equal(await display.textContent(), "05:00", "Starting a completed timer begins a fresh selected cycle.")
  await page.clock.fastForward(1000)
  assert.equal(await display.textContent(), "04:59")
  await reset.click()
  assert.equal(await display.textContent(), "05:00")
  checks++

  await work.click()
  await start.click()
  await start.click()
  await page.clock.fastForward(2000)
  assert.equal(await display.textContent(), "24:58", "Repeated start must not create another countdown.")
  const now = await page.evaluate(() => Date.now())
  await page.clock.setSystemTime(new Date(now + 31000))
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")))
  assert.equal(await display.textContent(), "24:27", "Returning to a suspended page must reconcile elapsed wall time.")
  checks++

  await rest.click()
  await start.click()
  const beforeDeadline = await page.evaluate(() => Date.now())
  await page.clock.setSystemTime(new Date(beforeDeadline + 301000))
  await pause.click()
  assert.equal(await display.textContent(), "00:00", "Pausing after the deadline must complete rather than extend the cycle.")
  assert.equal(await page.locator("#status").textContent(), "SEQUENCE COMPLETE.")
  checks++

  assert.deepEqual(errors, [])
  if (screenshot) await page.screenshot({ path: path.resolve(screenshot) })
  console.log(JSON.stringify({
    status: "passed", checks,
    source_sha256: createHash("sha256").update(source).digest("hex"),
    scope: "Actual Cyber Timer HTML in an offline isolated browser; reachable narrow/short-screen controls, throttled callbacks, pause/resume, modes, completion, restart and visibility reconciliation.",
  }))
} finally {
  await browser.close()
}
