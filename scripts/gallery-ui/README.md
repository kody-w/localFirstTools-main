# Liquid-glass gallery presentation

This is the React 19 + TypeScript + Tailwind CSS 4 + shadcn/Radix source package
for the gallery. It progressively enhances the existing static gallery instead
of replacing its catalog, community, voting, comments, previews, profiles or
standalone applications.

## Where components and styles live

| Purpose | Path relative to this package |
| --- | --- |
| Requested reusable component | `components/ui/liquid-glass-button.tsx` |
| Conventional shadcn Button export | `components/ui/button.tsx` |
| Supplied demo | `demo.tsx` |
| Component interaction examples | `components.html`, `src/component-examples.tsx` |
| Class-name helper | `lib/utils.ts` |
| Tailwind entry and token mappings | `src/index.css` |
| Light/dark design tokens | `src/theme.css` |
| Gallery layout and component surfaces | `src/gallery.css` |
| Gallery toolbar and appearance controls | `src/App.tsx` |
| Production HTML integration | `scripts/inject-gallery.mjs` |

`@/*` maps to this package's root in both TypeScript and Vite.
Therefore `@/components/ui/liquid-glass-button` resolves to the requested
`/components/ui` convention **within the React project**. The repository-level
path is `scripts/gallery-ui/components/ui`, not a new system `/components`
directory. Keeping this folder aligned with `components.json` makes CLI
generation and imports predictable; React itself does not require that name.

The package stays under `scripts/` because this repository reserves `apps/`
for standalone tools and auto-sorts stray HTML applications from its root.

## Build an existing checkout

Use Node 24 or newer:

```bash
# From the repository root
npm ci --prefix scripts/gallery-ui
npm run gallery:check
npm run gallery:build
python3 -m http.server 8768 --bind 127.0.0.1
```

Open `http://127.0.0.1:8768/`. Add `?scoutTheme=light` or `?scoutTheme=dark`
to select a theme explicitly. The appearance controls retain a local theme
and grid/list preference; an explicit URL theme takes precedence on load.

The build emits a production IIFE and stylesheet, then inlines them into the
marked `glass-gallery-styles` and `glass-gallery-script` regions of the root
`index.html`. Do not edit those generated regions by hand. Existing gallery
JavaScript and its native control IDs remain the data/interaction authority.

There are no runtime CDN modules, external fonts or npm requirements for visitors.
The decorative Unsplash image is locally bundled; attribution and its exact URL
are in `src/assets/credits.json`. Gallery JSON and application files remain
separate local repository data, so **the entry HTML alone is not a complete
offline copy of the platform**. A local clone served without Internet access
supports gallery browsing.

## Starting an equivalent React project from scratch

The repository did not previously have a React/shadcn gallery project.
For a new, empty directory the corresponding setup is:

```bash
npm create vite@latest scripts/gallery-ui -- --template react-ts --no-interactive --no-immediate
cd scripts/gallery-ui
npm install @radix-ui/react-slot class-variance-authority clsx tailwind-merge lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

Before initializing shadcn, add `@import "tailwindcss";` to `src/index.css`,
configure `@/*` as `["./*"]` in `tsconfig.json` and `tsconfig.app.json`, and
configure the same root alias plus `react()` and `tailwindcss()` in `vite.config.ts`.
Then initialize the Radix-backed preset:

```bash
npx shadcn@latest init --template vite --base radix --preset nova --no-monorepo --no-rtl --pointer --yes
```

This checkout already contains the generated configuration and the integrated
component. Use `npm ci`, not scaffolding or `--force`, for normal development.
Its theme intentionally replaces scaffold fonts/colors with the shared
`--cp-*` tokens and system typography.

Reference: <https://ui.shadcn.com/docs/installation/vite>.

## Component use

```tsx
import { LiquidButton, MetalButton } from "@/components/ui/liquid-glass-button"

<LiquidButton size="lg" onClick={openCollection}>Explore the collection</LiquidButton>
<LiquidButton asChild><a href="#featured">Featured finds</a></LiquidButton>
<MetalButton variant="primary" onClick={openAgent}>Bring your agent</MetalButton>
```

Exports retain `Button`, `buttonVariants`, `LiquidButton`,
`liquidbuttonVariants`, and `MetalButton`. The supplied component was adapted
for reusable production use:

- Each glass instance has a unique SVG filter ID.
- `asChild` uses Radix `Slottable` without creating invalid multiple-child slots.
- Disabled links cannot activate; native button semantics and forwarded refs remain.
- Metal pointer/keyboard state composes with caller handlers and resets on cancellation.
- Reduced motion disables transforms/transitions.
- Variant colors and layered surfaces use shared theme variables.

No context provider is required. Component-local interaction state uses React
hooks; gallery theme state is reflected in the root `data-theme` attribute.

## Browser exercise

The repository already uses Playwright. Restore that existing dependency with
`npm ci` at the repository root, then run the static server above and the component
example server in another terminal:

```bash
npm --prefix scripts/gallery-ui run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

From the root:

```bash
npm run gallery:test -- --url http://127.0.0.1:8768 \
  --components http://127.0.0.1:5174/components.html
python3 -m pytest -m '' scripts/tests/test_rappterzoo.py::TestFeed -q
```

The existing Moonshot gallery/Digg browser contract also runs in gallery CI,
including mutations that deliberately shrink both hero and below-the-fold vote
targets. Its 44px minimum is unchanged. To run that contract locally, restore
its existing browser dependency with `npx playwright install chromium` if needed,
then run `python3 -m pytest scripts/tests/test_moonshot_gate.py -k gallery_digg -q`.

`CHROME_BIN` may name an existing Chromium executable. The runner creates fresh
browser contexts; it never reuses a personal profile. It exercises actual built
gallery interactions, guest and agent onboarding, filters, details, theme/view
persistence, keyboard navigation, mobile menus with and without reduced motion,
the reusable component contracts, mobile geometry and a networking-disabled
local-data run. Optional `--screenshots DIRECTORY` captures desktop/mobile
light/dark images for inspection.

The layout borrows the navigation rhythm and framed-card grid from
<https://design-inspo-bay.vercel.app/#ui>. Its screenshots and content are not copied.
