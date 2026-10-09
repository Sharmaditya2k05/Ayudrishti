import { CircleUserRound, Menu, X } from 'lucide-react';
import { useState } from 'react';

const VIDEO_SRC =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260715_082433_69699cf8-444b-4484-93cc-053e57896dfd.mp4';

/*
 * Where the actual app lives.
 *
 * The landing page is a separate Vite build from the React Native app in
 * ../frontend, so the handoff between them is a URL, not an import -- the two
 * use different toolchains and cannot share a bundle. Override the target at
 * build time with VITE_APP_URL; the default is Expo's web dev-server port.
 */
const APP_URL =
  (import.meta.env.VITE_APP_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://localhost:8081';

type NavLink = { label: string; href: string; active?: boolean };

// "Home" stays on this page; the product links hand off into the app. They
// share a destination today because the RN app has no web deep-linking
// configured yet -- see the README for how to make them land on specific
// screens once it does.
const NAV_LINKS: NavLink[] = [
  { label: 'Home', href: '#top', active: true },
  { label: 'How It Works', href: APP_URL },
  { label: 'Asana Library', href: APP_URL },
];

const AVATARS = [
  'https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg?auto=compress&cs=tinysrgb&w=100',
  'https://images.pexels.com/photos/1222271/pexels-photo-1222271.jpeg?auto=compress&cs=tinysrgb&w=100',
  'https://images.pexels.com/photos/1239291/pexels-photo-1239291.jpeg?auto=compress&cs=tinysrgb&w=100',
  'https://images.pexels.com/photos/697509/pexels-photo-697509.jpeg?auto=compress&cs=tinysrgb&w=100',
];

/*
 * Nine dots in rows of 1 / 3 / 5, laid out by hand inside a 20x20 box.
 * A CSS grid cannot make a triangle without empty filler cells, so the
 * positions are explicit.
 */
const TRIANGLE_DOTS: { left: number; top: number }[] = [
  { left: 8.75, top: 1 },
  { left: 4.5, top: 8 },
  { left: 8.75, top: 8 },
  { left: 13, top: 8 },
  { left: 0.25, top: 15 },
  { left: 4.5, top: 15 },
  { left: 8.75, top: 15 },
  { left: 13, top: 15 },
  { left: 17.25, top: 15 },
];

function Logo() {
  return (
    <svg
      viewBox="0 0 256 256"
      className="h-8 w-8 md:h-9 md:w-9"
      fill="white"
      aria-hidden="true"
    >
      <path d="M 128 128 C 198.692 128 256 185.308 256 256 L 151.883 256 C 149.812 220.307 120.213 192 84 192 C 47.787 192 18.188 220.307 16.117 256 L 0 256 C 0 185.308 57.308 128 128 128 Z M 104.117 0 C 106.188 35.694 135.787 64 172 64 C 208.213 64 237.812 35.694 239.883 0 L 256 0 C 256 70.692 198.692 128 128 128 C 57.308 128 0 70.692 0 0 Z" />
    </svg>
  );
}

function TriangleIcon() {
  return (
    <div className="relative h-5 w-5" aria-hidden="true">
      {TRIANGLE_DOTS.map((dot, i) => (
        <span
          key={i}
          className="absolute bg-white/60"
          style={{
            left: `${dot.left}px`,
            top: `${dot.top}px`,
            width: '2.5px',
            height: '2.5px',
          }}
        />
      ))}
    </div>
  );
}

function GridIcon() {
  return (
    <div className="grid grid-cols-3 gap-[2px]" aria-hidden="true">
      {Array.from({ length: 9 }).map((_, i) => {
        const row = Math.floor(i / 3);
        const col = i % 3;
        // Checkerboard: corners and centre filled, edges empty.
        const filled = (row + col) % 2 === 0;
        return (
          <span
            key={i}
            className={`h-1 w-1 rounded-[1px] ${filled ? 'bg-white/60' : 'bg-white/0'}`}
          />
        );
      })}
    </div>
  );
}

/*
 * A heartbeat/ECG blip: five bars of increasing-then-decreasing height,
 * built the same way as TriangleIcon and GridIcon (plain white/60 bars, no
 * icon library) so the third stat reads as part of the same hand-drawn set.
 */
const PULSE_BAR_HEIGHTS = [3, 6, 14, 8, 4];

function PulseIcon() {
  return (
    <div className="flex h-5 w-5 items-end gap-[1.5px]" aria-hidden="true">
      {PULSE_BAR_HEIGHTS.map((height, i) => (
        <span
          key={i}
          className="w-[2.5px] rounded-[1px] bg-white/60"
          style={{ height: `${height}px` }}
        />
      ))}
    </div>
  );
}

function Stat({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
}) {
  return (
    <div>
      <div className="mb-2 sm:mb-3">{icon}</div>
      {/* Value in mono (like the app's stat figures), label in mono uppercase */}
      <div className="font-mono text-xl text-white sm:text-2xl md:text-3xl">{value}</div>
      <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-white/55 sm:text-[11px]">
        {label}
      </div>
    </div>
  );
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <section id="top" className="relative h-screen w-full overflow-hidden">
      {/* Background video */}
      <video
        className="absolute inset-0 h-full w-full object-cover"
        src={VIDEO_SRC}
        autoPlay
        loop
        muted
        playsInline
        // Decorative: the page reads identically without it.
        aria-hidden="true"
      />

      {/* Legibility scrim. The glass elements blur what is behind them, but
          plain text over bright video frames still needs help. */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/40 via-black/20 to-black/50" />

      <div className="relative z-10 flex h-full flex-col">
        {/* ---------------------------------------------------------------- */}
        {/* Navigation                                                        */}
        {/* ---------------------------------------------------------------- */}
        <nav className="relative z-20 flex items-center justify-between px-5 pt-6 sm:px-8 sm:pt-8 md:px-16 lg:px-20">
          <a href="#" aria-label="AyuDrishti home" className="flex items-center gap-3">
            <Logo />
            <span className="hidden font-serif text-2xl leading-none text-white sm:inline">
              AyuDrishti
            </span>
          </a>

          {/* Desktop nav pill -- mono uppercase links, matching the app's labels */}
          <div className="liquid-glass hidden rounded-full px-8 py-3 md:block">
            <div className="flex items-center gap-8">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className={`font-mono text-[11px] uppercase tracking-[0.18em] transition-opacity duration-300 ${
                    link.active ? 'text-white' : 'text-white/60 hover:opacity-100'
                  }`}
                >
                  {link.label}
                </a>
              ))}
            </div>
          </div>

          {/* Desktop account -- links into the app's sign-in. */}
          <a
            href={APP_URL}
            aria-label="Sign in to AyuDrishti"
            className="liquid-glass hidden h-10 w-10 items-center justify-center rounded-full md:flex"
          >
            <CircleUserRound className="h-5 w-5 text-white/80" strokeWidth={1.5} />
          </a>

          {/* Mobile menu toggle */}
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            className="liquid-glass relative z-50 flex h-10 w-10 items-center justify-center rounded-full md:hidden"
          >
            {/* Both icons stay mounted and cross-fade, so the swap animates
                instead of popping. */}
            <Menu
              className={`absolute h-5 w-5 text-white/80 transition-all duration-300 ${
                menuOpen ? 'rotate-90 scale-0 opacity-0' : 'rotate-0 scale-100 opacity-100'
              }`}
              strokeWidth={1.5}
            />
            <X
              className={`absolute h-5 w-5 text-white/80 transition-all duration-300 ${
                menuOpen ? 'rotate-0 scale-100 opacity-100' : 'rotate-90 scale-0 opacity-0'
              }`}
              strokeWidth={1.5}
            />
          </button>
        </nav>

        {/* ---------------------------------------------------------------- */}
        {/* Mobile menu overlay                                               */}
        {/* ---------------------------------------------------------------- */}
        <div
          className={`fixed inset-0 z-10 bg-black/80 backdrop-blur-xl transition-opacity duration-500 ease-out md:hidden ${
            menuOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
          }`}
        >
          <div
            className={`flex h-full flex-col items-center justify-center gap-8 transition-transform duration-500 ease-out ${
              menuOpen ? 'translate-y-0' : '-translate-y-8'
            }`}
          >
            {NAV_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className={`font-mono text-lg uppercase tracking-[0.16em] ${
                  link.active ? 'text-white' : 'text-white/70'
                }`}
              >
                {link.label}
              </a>
            ))}

            <a
              href={APP_URL}
              onClick={() => setMenuOpen(false)}
              className="mt-4 flex flex-col items-center gap-3"
            >
              <div className="liquid-glass flex h-10 w-10 items-center justify-center rounded-full">
                <CircleUserRound className="h-5 w-5 text-white/80" strokeWidth={1.5} />
              </div>
              <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/60">
                Account
              </span>
            </a>
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Main content                                                      */}
        {/* ---------------------------------------------------------------- */}
        <main
          className={`z-10 flex flex-1 flex-col justify-between px-5 pb-8 sm:px-8 sm:pb-10 md:px-16 md:pb-14 lg:px-20 ${
            menuOpen ? 'pointer-events-none opacity-0 md:pointer-events-auto md:opacity-100' : 'opacity-100'
          } transition-opacity duration-300`}
        >
          {/* Top block */}
          <div className="mt-14 max-w-2xl sm:mt-20 md:mt-28">
            {/* Badge */}
            <div className="liquid-glass mb-5 inline-flex items-center gap-2.5 rounded-full px-3 py-1.5 sm:mb-6 sm:gap-3 sm:px-4 sm:py-2">
              <div className="flex -space-x-2">
                {/* Above the fold, so these load eagerly: lazy-loading hero
                    imagery only delays it for no bandwidth saving. */}
                {AVATARS.map((src, i) => (
                  <img
                    key={src}
                    src={src}
                    alt=""
                    aria-hidden="true"
                    loading="eager"
                    decoding="async"
                    className="h-5 w-5 rounded-full border-2 border-white/20 object-cover sm:h-6 sm:w-6"
                    style={{ zIndex: AVATARS.length - i }}
                  />
                ))}
              </div>
              <span className="text-xs font-light text-white/80 sm:text-sm">
                your path to better alignment
              </span>
            </div>

            {/* Heading -- Instrument Serif, the app's display face. The serif
                sets its own line-height per Tailwind size, so leading is
                repeated at each breakpoint to hold it steady. */}
            <h1
              className="font-serif text-5xl leading-[1.02] text-white sm:text-6xl sm:leading-[1.02] md:text-7xl md:leading-[1.02] lg:text-8xl lg:leading-[1.02]"
              style={{ letterSpacing: '-0.01em' }}
            >
              Every Pose,
              <br />
              Perfectly Aligned
            </h1>

            {/* Subtitle -- mono uppercase, echoing the app's eyebrow labels */}
            <p className="mt-5 font-mono text-[11px] uppercase leading-relaxed tracking-[0.16em] text-white/70 sm:mt-6 sm:text-xs">
              Real-time posture assessment · Corrections you can act on
            </p>

            {/* CTA -- an anchor, not a button: this navigates into the app,
                so right-click, middle-click and open-in-new-tab all work. */}
            <a
              href={APP_URL}
              className="liquid-glass mt-7 inline-block rounded-full px-7 py-3.5 font-mono text-[11px] uppercase tracking-[0.18em] text-white transition duration-300 hover:bg-white/10 sm:mt-9 sm:px-8 sm:py-4"
            >
              Start Your Session
            </a>
          </div>

          {/* Bottom stats. Gap is tighter than a 2-up row would need, since a
              third stat has to fit the same width on mobile. */}
          <div className="flex items-end gap-4 sm:gap-8 md:gap-14">
            <Stat icon={<TriangleIcon />} value="10 Asanas" label="Pose Library" />
            <Stat icon={<GridIcon />} value="82 Checks" label="Alignment Rules" />
            {/* Matches the safety layer's actual signal set: heart rate, SpO2,
                GSR and motion (ai/safety/safety.py's PhysiologicalSnapshot) --
                optional wearable, works without one. */}
            <Stat icon={<PulseIcon />} value="4 Signals" label="Safety Monitoring" />
          </div>
        </main>
      </div>
    </section>
  );
}
