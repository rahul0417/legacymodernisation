# Panasa Modernisation Cockpit

A live-feel demo of Panasa's seven-stage AI-supervised legacy modernisation pipeline, built for 1:1 prospect demos.

## Demo flow

A click-to-advance walkthrough of a PHP monolith → Java 21 microservices migration for a fictional neobank. Each stage runs an AI agent visibly (todo list streams), produces real artefacts (sidebar fills up), and at Self Review pauses for a named human engineer to review three flagged items before the pipeline continues.

The substance of the demo lives in the Comprehension stage's relationship diagram — 13 extracted artefact types (System, Software, Screens, Functions, Database Tables, Business Rules, User Stories, etc.) with labelled relationships, where every node clicks through to evidence pointers in the legacy source code.

## Running locally

It's a single static HTML file. Open `index.html` in a browser, or:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

## Keyboard

- `→` / `Enter` / `Space` — advance the pipeline
- `R` — reset

## Customising for a real prospect

Before any prospect demo, swap these:

- **Engagement name** (top bar) — replace "NeoBank Core Banking Platform" with the prospect's system name
- **Tech stack** (top bar) — adjust the from/to (e.g. "Legacy .NET Framework" → ".NET 8 Microservices")
- **Reviewer name** (Self Review stage) — replace "Ramesh Bhat" with whichever Panasa principal will lead the engagement
- **Evidence file paths** (in the `EVIDENCE` constant near the top of the script) — replace with real paths from a similar past engagement (Osper would be a strong choice for open banking prospects)

All these are string constants in `index.html`; search-and-replace is enough.

## Deployment

Deployed via Vercel from this repo. Pushes to `main` auto-deploy.
