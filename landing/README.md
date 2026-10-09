# AyuDrishti — landing page

A scrolling marketing page: a parallax hero with the app preview blended over
video, then a scroll-revealed testimonial. React + Vite + TypeScript + Tailwind
+ Framer Motion, with shadcn-style UI primitives.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # typecheck + production bundle into dist/
npm run typecheck
```

A separate build from the app in `../frontend` (different toolchains cannot
share a bundle). It **hands off** to the app by URL — see below.

## Structure

- **Hero** (`src/components/Hero.tsx`) — navbar, liquid-glass tag pill, title
  with an Instrument Serif italic accent word, subtitle, CTA, and a full-bleed
  video with the app preview blended over it (`mix-blend-mode: luminosity`).
  Framer Motion drives staggered entrance animations and two scroll-linked
  parallax effects (`useScroll` + `useTransform`): the text drifts up and
  fades over the first half of the scroll; the preview drifts faster.
- **Testimonial** (`src/components/Testimonial.tsx`) — a quote whose words
  brighten one by one as the block scrolls through the viewport, each word a
  `motion.span` mapped to its own slice of the scroll progress.
- **AppPreview** (`src/components/AppPreview.tsx`) — an inline SVG mockup of the
  AyuDrishti live-session screen (score ring, alignment bars, flagged knee),
  standing in for a screenshot so the page needs no binary asset and stays on
  brand.

## Design system

Built to the given SaaS spec — pure-black theme, white text, Inter body,
Instrument Serif italic accent, liquid glass — adapted to AyuDrishti. The
tokens are HSL channels on `:root` in `src/index.css`, composed through
Tailwind (`bg-background`, `text-muted-foreground`, …).

Two threads tie it to the app it hands off to:

- **Instrument Serif** — the accent word here, the display face in the app.
- **`--accent` violet** (`265 100% 83%` = `#C6A8FF`) — the app's accent, used
  on the italic accent word so the brand carries across.

Fonts are self-hosted via `@fontsource` (spec), not a CDN link.

## Handoff to the app

Both **Sign In** and **Start Your Session** navigate to the app. The target is
configurable:

```bash
# landing/.env — defaults to Expo's web dev port when unset
VITE_APP_URL=http://localhost:8081
```

Run both to see the whole path:

```bash
cd ../frontend && npm run web     # app on http://localhost:8081
npm run dev                       # landing on http://localhost:5173
```

## Notes

- **The scroll/entrance animations need a visible tab.** Framer Motion drives
  them via `requestAnimationFrame`, which browsers suspend for hidden or
  non-composited tabs — so an automated/headless check sees them frozen at
  their initial state even though the wiring is correct. Open the page in a
  real browser to see them run.
- **The video is decorative** (`aria-hidden`) and muted, which is also what
  browsers require for autoplay.
- Swap the video URL and testimonial avatar (both third-party hosted) at the
  top of their components to self-host.
