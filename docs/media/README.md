# Demo media — shot list (to record)

Drop the recorded assets here and un-comment the `![demo](docs/media/demo.gif)`
line in the top-level README.

## `demo.gif` — the hero loop (≤ 20s, looping, ~1000px wide)
The single GIF that sells the repo. Record in Claude Code:

1. Type: *"List the WebRobot ETL stages and draft a pipeline to scrape product
   titles and prices from an e-commerce page."*
2. Show the agent calling the WebRobot MCP (catalog → draft pipeline YAML).
3. Validate on a real browser, then run; show a few result rows.
4. End on the result (and optionally a chart).

Keep it tight: trim dead time, 12–18s, loop cleanly. Tools: `asciinema`+`agg`,
`peek`, or `vhs` (charmbracelet) for a scripted terminal GIF.

## Optional extras
- `mcp.gif` — `/plugin marketplace add …` → tools appear (the 30-second install).
- `chart.gif` — "make a chart of the results" → Vega-Lite renders.
- `social-preview.png` — 1280×640 repo social image (Settings → Social preview).
