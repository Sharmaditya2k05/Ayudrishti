# Troubleshooting

## Frontend

### `Requiring unknown module "1050"` (or any module number)

Metro assigns numeric ids to modules and caches the mapping. Installing,
removing or upgrading a dependency renumbers them, and a cached bundle then
asks for an id that no longer exists.

```bash
cd frontend && npm run web -- --clear
```

Run this after any `npm install`. It is not a fault in the app code.

### `CommandError: It looks like you're trying to use web support but don't have the required dependencies installed`

`@expo/metro-runtime` is missing. It is declared in `package.json`, so:

```bash
cd frontend && npm install
```

### The app loads but every request fails

The backend is not running, or the app is pointing at the wrong host.

- Start it: `uvicorn backend.main:app --reload --port 8000`
- Check it: `curl http://localhost:8000/health`
- **Android emulator** reaches the host machine at `10.0.2.2`, not
  `localhost` — the API client already handles this, but a hard-coded
  `EXPO_PUBLIC_API_BASE_URL` in `.env` will override it.
- **Physical device**: set `EXPO_PUBLIC_API_BASE_URL` to your machine's LAN
  IP and make sure the backend binds `0.0.0.0`, not just localhost.

### The camera never starts on web

Browsers only expose `getUserMedia` over HTTPS or on `localhost`. Opening the
dev server via a LAN IP will silently fail. Also check the browser's own
camera permission for the site.

### `npm install` reports vulnerabilities

These come from the Expo 51 / React Native transitive dependency tree, not
from this project's code. **Do not run `npm audit fix --force`** — it bumps
packages past the versions Expo SDK 51 pins and breaks the build. The real
fix is a deliberate Expo SDK upgrade.

## Backend

### `Running on SQLite ... development fallback only`

`DATABASE_URL` is unset. Fine for tests and a first look; set it to your
PostgreSQL instance for anything else.

### Tokens stop working after every restart

`SECRET_KEY` is unset, so a random one is generated per process. Set it in
`.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### `428 Precondition Required` from `/recommendations`

The account has not completed onboarding. Recommendations need goals and an
experience level — without them any plan would be arbitrary, so the endpoint
asks rather than guesses.

## Pose pipeline

### `DetectorUnavailable: no pose backend could be started`

MediaPipe 1.x removed the bundled-weights Solutions API and needs a model
file:

```bash
python scripts/fetch_models.py
```

### Poses score low no matter what you do

Check the camera angle. Some asanas can only be judged from the side — knee
flexion in Chair Pose is foreshortened to nothing head-on. Each asana
declares a `preferred_view` and `camera_hint`:

```bash
python scripts/live_session.py --list
```

If joints are out of frame the assessment says so explicitly and lowers its
reported confidence rather than inventing measurements — check the
`missing_landmarks` and `notes` fields in the response.
