import { useEffect, useState } from "react"
import { ArrowRight, Compass, Grid2X2, List, Moon, Sparkles, Sun } from "lucide-react"
import { Button, LiquidButton, MetalButton } from "@/components/ui/liquid-glass-button"
import landscape from "./assets/gallery-landscape.jpg"

type Theme = "light" | "dark"
type View = "grid" | "list"

export default function App() {
  const [theme, setTheme] = useState<Theme>(document.documentElement.dataset.theme === "dark" ? "dark" : "light")
  const [view, setView] = useState<View>("grid")
  const [count, setCount] = useState<number | null>(null)
  const [status, setStatus] = useState("")

  useEffect(() => {
    const forced = new URLSearchParams(window.location.search).get("scoutTheme")
    try {
      const savedTheme = localStorage.getItem("rappterzoo-gallery-theme")
      const savedView = localStorage.getItem("rappterzoo-gallery-view")
      if (forced !== "light" && forced !== "dark" && (savedTheme === "light" || savedTheme === "dark")) setTheme(savedTheme)
      if (savedView === "list" || savedView === "grid") setView(savedView)
    } catch {
      setStatus("Preferences are available for this visit; browser storage is unavailable.")
    }
    const counter = document.getElementById("ct")
    if (!counter) return
    const update = () => {
      const value = Number(counter.textContent)
      if (Number.isFinite(value) && value > 0) setCount(value)
    }
    update()
    const observer = new MutationObserver(update)
    observer.observe(counter, { childList: true, characterData: true, subtree: true })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.classList.toggle("dark", theme === "dark")
  }, [theme])

  useEffect(() => {
    document.documentElement.dataset.galleryView = view
  }, [view])

  function savePreference(key: string, value: string) {
    try { localStorage.setItem(key, value) }
    catch { setStatus("Changed for this visit. Your browser could not save the preference.") }
  }

  function browse() {
    const input = document.getElementById("q")
    if (!input) { setStatus("Search is not available yet."); return }
    input.focus()
    setStatus("Search by title, description, or tag. Press / to return here.")
  }

  function featured() {
    const filter = document.querySelector<HTMLButtonElement>('#sidebar [data-c="featured"]')
    if (!filter || count === null) { setStatus("The catalog is still loading."); return }
    filter.click()
    document.querySelector(".sort-bar")?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    })
    setStatus("Showing the featured collection. Choose All Apps to see everything again.")
  }

  function sendAgent() {
    const action = document.getElementById("gallery-send-agent")
    if (!action) { setStatus("Agent onboarding is not available yet."); return }
    action.click()
  }

  return (
    <>
      <section className="glass-hero" aria-labelledby="gallery-heading">
        <div className="glass-intro">
          <p className="glass-eyebrow">RappterZoo / your browser, expanded</p>
          <h1 id="gallery-heading">Small tools.<br /><span>Wide-open possibilities.</span></h1>
          <p className="glass-description">
            A living collection of useful tools, playful experiments, and worlds to get lost in.
            Find something good. Open it. Make it yours.
          </p>
          <div className="glass-actions">
            <LiquidButton size="lg" onClick={browse} aria-label="Explore the collection">
              <Compass aria-hidden="true" /> Explore the collection <ArrowRight aria-hidden="true" />
            </LiquidButton>
            <MetalButton variant="default" onClick={sendAgent}>
              <Sparkles aria-hidden="true" /> Bring your agent
            </MetalButton>
          </div>
          <p className="glass-status" role="status" aria-live="polite">{status}</p>
        </div>
        <div className="glass-card">
          <img className="glass-card-image" src={landscape} alt="" />
          <div className="glass-card-overlay" aria-hidden="true" />
          <div className="glass-card-content">
            <span className="glass-count">{count === null ? "A growing collection" : `${count.toLocaleString()} apps to explore`}</span>
            <div className="glass-card-caption">
              <h2>Take the scenic route.</h2>
              <p>Start with the collection's featured finds.</p>
            </div>
            <LiquidButton size="default" variant="outline" onClick={featured} disabled={count === null}>
              Featured finds <ArrowRight aria-hidden="true" />
            </LiquidButton>
          </div>
        </div>
      </section>
      <div className="glass-utility">
        <div>
          <p className="glass-eyebrow">The collection</p>
          <p>Browse by category. Hover for a live preview. Open a card for the full story.</p>
        </div>
        <div className="glass-view-controls" aria-label="Gallery appearance">
          <Button
            variant={view === "grid" ? "secondary" : "ghost"} size="icon"
            aria-label="Grid view" aria-pressed={view === "grid"}
            onClick={() => { setView("grid"); savePreference("rappterzoo-gallery-view", "grid") }}
          ><Grid2X2 aria-hidden="true" /></Button>
          <Button
            variant={view === "list" ? "secondary" : "ghost"} size="icon"
            aria-label="List view" aria-pressed={view === "list"}
            onClick={() => { setView("list"); savePreference("rappterzoo-gallery-view", "list") }}
          ><List aria-hidden="true" /></Button>
          <Button
            variant="outline" size="icon"
            aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}
            onClick={() => {
              const next = theme === "dark" ? "light" : "dark"
              setTheme(next)
              savePreference("rappterzoo-gallery-theme", next)
            }}
          >{theme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}</Button>
        </div>
      </div>
    </>
  )
}
