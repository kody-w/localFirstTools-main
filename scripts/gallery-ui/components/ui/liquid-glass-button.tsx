"use client"

import * as React from "react"
import { Slot, Slottable } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 motion-reduce:transition-none",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-primary-foreground hover:bg-destructive/90",
        cool: "button-cool bg-primary text-primary-foreground transition-[filter] duration-200 hover:brightness-110 active:brightness-90",
        outline: "border border-input bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "text-foreground hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-md px-8",
        icon: "size-11",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, disabled, onClickCapture, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        {...props}
        ref={ref}
        type={asChild ? undefined : type ?? "button"}
        disabled={asChild ? undefined : disabled}
        aria-disabled={disabled || props["aria-disabled"]}
        tabIndex={asChild && disabled ? -1 : props.tabIndex}
        className={cn(buttonVariants({ variant, size, className }))}
        onClickCapture={(event) => {
          if (disabled) {
            event.preventDefault()
            event.stopPropagation()
            return
          }
          onClickCapture?.(event)
        }}
      />
    )
  },
)
Button.displayName = "Button"

const liquidbuttonVariants = cva(
  "relative isolate inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium outline-none transition-[color,box-shadow,transform] duration-300 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 motion-reduce:transform-none motion-reduce:transition-none",
  {
    variants: {
      variant: {
        default: "liquid-default bg-[var(--cp-panel)] text-primary hover:scale-[1.03] active:scale-[0.98]",
        destructive: "bg-destructive text-primary-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background text-foreground hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "bg-transparent text-foreground hover:bg-accent",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-11 px-5 py-2",
        sm: "h-9 gap-1.5 px-4 text-xs",
        lg: "h-12 px-6",
        xl: "h-12 px-8",
        xxl: "h-14 px-10",
        icon: "size-11",
      },
    },
    defaultVariants: { variant: "default", size: "xxl" },
  },
)

type LiquidButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof liquidbuttonVariants> & { asChild?: boolean }

const LiquidButton = React.forwardRef<HTMLButtonElement, LiquidButtonProps>(
  ({ className, variant, size, asChild = false, children, disabled, type, onClickCapture, ...props }, ref) => {
    const filterId = `container-glass-${React.useId().replace(/:/g, "")}`
    const Comp = asChild ? Slot : "button"
    let content: React.ReactNode = <span className="liquid-content">{children}</span>
    if (asChild) {
      const child = React.Children.only(children)
      if (!React.isValidElement<{ children?: React.ReactNode }>(child) || child.type === React.Fragment) {
        throw new Error("LiquidButton asChild requires one element, not a fragment.")
      }
      content = React.cloneElement(child, {}, <span className="liquid-content">{child.props.children}</span>)
    }
    return (
      <>
        <Comp
          {...props}
          ref={ref}
          data-slot="button"
          data-liquid-button=""
          type={asChild ? undefined : type ?? "button"}
          disabled={asChild ? undefined : disabled}
          aria-disabled={disabled || props["aria-disabled"]}
          tabIndex={asChild && disabled ? -1 : props.tabIndex}
          className={cn(liquidbuttonVariants({ variant, size, className }))}
          onClickCapture={(event) => {
            if (disabled) {
              event.preventDefault()
              event.stopPropagation()
              return
            }
            onClickCapture?.(event)
          }}
        >
          <span aria-hidden="true" className="liquid-backdrop" style={{ backdropFilter: `blur(10px) url("#${filterId}")` }} />
          <span aria-hidden="true" className="liquid-surface" />
          <Slottable>{content}</Slottable>
        </Comp>
        <GlassFilter id={filterId} />
      </>
    )
  },
)
LiquidButton.displayName = "LiquidButton"

function GlassFilter({ id }: { id: string }) {
  return (
    <svg aria-hidden="true" focusable="false" width="0" height="0" className="glass-filter-definition">
      <defs>
        <filter id={id} x="0%" y="0%" width="100%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.05 0.05" numOctaves="1" seed="1" result="turbulence" />
          <feGaussianBlur in="turbulence" stdDeviation="2" result="blurredNoise" />
          <feDisplacementMap in="SourceGraphic" in2="blurredNoise" scale="70" xChannelSelector="R" yChannelSelector="B" result="displaced" />
          <feGaussianBlur in="displaced" stdDeviation="4" result="finalBlur" />
          <feComposite in="finalBlur" in2="finalBlur" operator="over" />
        </filter>
      </defs>
    </svg>
  )
}

type ColorVariant = "default" | "primary" | "success" | "error" | "gold" | "bronze"
export interface MetalButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ColorVariant
}

const MetalButton = React.forwardRef<HTMLButtonElement, MetalButtonProps>(
  ({
    children, className, variant = "default", disabled, type, style,
    onPointerDown, onPointerUp, onPointerEnter, onPointerLeave, onPointerCancel,
    onLostPointerCapture, onKeyDown, onKeyUp, onBlur, ...props
  }, ref) => {
    const [pressed, setPressed] = React.useState(false)
    const [hovered, setHovered] = React.useState(false)
    React.useEffect(() => { if (disabled) { setPressed(false); setHovered(false) } }, [disabled])
    return (
      <span
        className="metal-wrapper"
        data-metal-variant={variant}
        data-pressed={!disabled && pressed}
        data-hovered={!disabled && hovered}
        data-disabled={Boolean(disabled)}
      >
        <span className="metal-inner" aria-hidden="true" />
        <button
          {...props}
          ref={ref}
          type={type ?? "button"}
          disabled={disabled}
          style={style}
          className={cn("metal-button", className)}
          onPointerDown={(event) => {
            onPointerDown?.(event)
            if (!disabled && !event.defaultPrevented && event.button === 0) {
              setPressed(true)
            }
          }}
          onPointerUp={(event) => { setPressed(false); onPointerUp?.(event) }}
          onPointerEnter={(event) => {
            if (!disabled && event.pointerType === "mouse") setHovered(true)
            onPointerEnter?.(event)
          }}
          onPointerLeave={(event) => { setHovered(false); setPressed(false); onPointerLeave?.(event) }}
          onPointerCancel={(event) => { setPressed(false); onPointerCancel?.(event) }}
          onLostPointerCapture={(event) => { setPressed(false); onLostPointerCapture?.(event) }}
          onKeyDown={(event) => {
            onKeyDown?.(event)
            if (!disabled && !event.defaultPrevented && (event.key === " " || event.key === "Enter")) setPressed(true)
          }}
          onKeyUp={(event) => { setPressed(false); onKeyUp?.(event) }}
          onBlur={(event) => { setPressed(false); setHovered(false); onBlur?.(event) }}
        >
          <span className="metal-shine" aria-hidden="true" />
          <span className="metal-content">{children ?? "Button"}</span>
        </button>
      </span>
    )
  },
)
MetalButton.displayName = "MetalButton"

export { Button, buttonVariants, liquidbuttonVariants, LiquidButton, MetalButton }
