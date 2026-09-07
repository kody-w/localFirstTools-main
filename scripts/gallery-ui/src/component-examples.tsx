import { useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import { ArrowRight } from "lucide-react"
import { Button, LiquidButton, MetalButton } from "@/components/ui/liquid-glass-button"
import DemoOne from "../demo"
import "./index.css"

function Examples() {
  const [clicks, setClicks] = useState(0)
  const [pointerEvents, setPointerEvents] = useState(0)
  const ref = useRef<HTMLButtonElement>(null)
  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-4 text-3xl font-semibold">Liquid glass component examples</h1>
      <p role="status">Clicks: <span data-clicks>{clicks}</span>; pointer callbacks: <span data-pointers>{pointerEvents}</span></p>
      <div className="my-6 flex flex-wrap items-center gap-4">
        <LiquidButton ref={ref} onClick={() => setClicks(value => value + 1)}>Liquid action</LiquidButton>
        <LiquidButton asChild><a href="#destination" onClick={() => setClicks(value => value + 1)}>Slotted link <ArrowRight /></a></LiquidButton>
        <LiquidButton disabled onClick={() => setClicks(value => value + 100)}>Disabled liquid</LiquidButton>
        <LiquidButton asChild disabled><a href="#blocked" onClick={() => setClicks(value => value + 100)}>Disabled link</a></LiquidButton>
        <Button variant="outline" onClick={() => ref.current?.focus()}>Focus forwarded ref</Button>
      </div>
      <div className="my-6 flex flex-wrap gap-4">
        {(["default", "primary", "success", "error", "gold", "bronze"] as const).map(variant => (
          <MetalButton key={variant} variant={variant}
            onClick={() => setClicks(value => value + 1)}
            onPointerDown={() => setPointerEvents(value => value + 1)}>
            Metal {variant}
          </MetalButton>
        ))}
        <MetalButton disabled onClick={() => setClicks(value => value + 100)}>Disabled metal</MetalButton>
      </div>
      <div className="my-6 flex flex-wrap gap-4">
        {(["default", "destructive", "cool", "outline", "secondary", "ghost", "link"] as const).map(variant => (
          <Button key={variant} variant={variant} onClick={() => setClicks(value => value + 1)}>Button {variant}</Button>
        ))}
      </div>
      <DemoOne />
      <p id="destination">A real anchor destination.</p>
    </main>
  )
}

const root = document.getElementById("component-examples")
if (!root) throw new Error("Component example root is missing.")
createRoot(root).render(<Examples />)
