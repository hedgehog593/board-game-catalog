# Changelog

## v1.2 - 2026-10-15

- Add Chromium journeys for Finder, Randomizer, Admin, and responsive dropdowns.
- Add API tests for authentication, filtering, CSV syncing, and metadata retention.
- Cover BGG fetching, parsing, batching, queued responses, rate limits, and failures.
- Add an optional live BGG integration check using a disposable catalog.
- Run automated tests during Docker builds and in GitHub Actions.
- Keep live credentials in BuildKit secrets and exclude browser artifacts from Git.
- Make local setup instructions portable.

## v1.1

- Add colorful board game styling and a slot machine randomizer with a handle.
- Add searchable filters, genre clearing, and responsive dropdown layouts.
- Preserve BGG metadata when syncing the owned-game CSV.

## v1.0

- Initial SQLite catalog, Python API, Finder, Admin, and Randomizer.
