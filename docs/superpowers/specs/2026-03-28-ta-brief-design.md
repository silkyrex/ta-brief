# ta-brief Design Spec
**Date:** 2026-03-28

## Purpose

The momentum trading system at `~/trading/` detects algorithmic signals (4 EMA reclaim, RSI cross, volume thresholds) but has no systematic way to assess the qualitative layer: narrative, sector theme, institutional buzz. These account for 20pts of the 100pt athlete scorecard (Theme/Leadership + implicit approval context). Currently this is pure gut feel.

`ta-brief` is a standalone CLI tool that reads articles and transcripts from a Notion database, processes them through the full momentum system criteria, and outputs a structured TA brief as markdown. It is the front-of-funnel intelligence layer that feeds the trading system's watchlist and informs human approval decisions.

---

## Architecture

```
Notion database (user adds articles/transcripts)
        ↓
ta_brief.py run
        ↓
notion.py — fetch net-new pages (by notion_id vs local SQLite)
        ↓
token check — < 150K chars: direct to Opus
              ≥ 150K chars: summarize each page with Haiku first
        ↓
Claude (Opus) — full TA criteria from prompt.py + last 3 briefs as context
        ↓
briefings/YYYY-MM-DD.md
        ↓
SQLite — mark pages as processed
```

---

## Commands

| Command | Action |
|---|---|
| `python ta_brief.py run` | Sync net-new Notion pages + generate brief (primary) |
| `python ta_brief.py sync` | Fetch only, no brief generation |
| `python ta_brief.py brief` | Generate brief from already-synced pages, no Notion call |

---

## File Structure

```
~/ta-brief/
├── ta_brief.py          # CLI entry point + orchestration
├── notion.py            # Notion API client (fetch pages, parse blocks)
├── prompt.py            # Full TA criteria prompt (momentum system)
├── requirements.txt
├── .env.example
├── .gitignore
├── ta_brief.db          # SQLite (runtime, gitignored)
├── briefings/           # markdown output (runtime, gitignored)
└── docs/superpowers/specs/
    └── 2026-03-28-ta-brief-design.md
```

---

## SQLite Schema

```sql
CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    notion_id TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    fetched_at TEXT,
    processed_at TEXT  -- NULL until included in a brief
);

CREATE TABLE briefs (
    id INTEGER PRIMARY KEY,
    date TEXT,
    filepath TEXT,
    content TEXT,
    created_at TEXT
);
```

---

## Brief Output Format

```markdown
# TA Brief — YYYY-MM-DD

## Market Read
Narrative: sector themes, regime signals, macro tailwinds/headwinds across all articles.

## Tickers Flagged

### TICKER — Tier N Candidate (est. XX/100)
**Signals observed:** 4 EMA reclaim / RSI cross / weekly base breakout / bull snort
**Athlete score breakdown:** Weekly structure X/25, Expansion X/20, Volume X/20, Rest X/15, Theme X/10, Asymmetry X/10
**Key quotes:** "[relevant excerpt]"
**Watch for:** entry trigger / setup type

## Signals Without Tickers
Sector ETF observations, macro TA reads, group confirmation themes.

## Historical Context
Confirmation or contradiction of prior brief flags.
```

---

## prompt.py Encodes

Full momentum system from CLAUDE.md:
- Athlete scorecard: 6 categories, point values, tier thresholds (85+ T1, 70-84 T2, 55-69 watch, <55 reject)
- Signal definitions: bull snort, fresh reclaim, rest condition, extended setup
- Entry asymmetry rules
- Exit rules (Day 1 discretionary, Day 2 mandatory)
- Constraint: only score what can be inferred from article text — no fabricated signals

---

## Phased Rollout

| Phase | Description |
|---|---|
| 1 (this build) | Standalone tool: Notion → SQLite → Claude → markdown |
| 2 | Watchlist integration: surface ≥70 candidates for ~/trading/watchlist.txt |
| 3 | Approval context: include ta-brief mentions in trigger_agent.py Discord alerts |
| 4 | Athlete scorecard enrichment: qualitative scores pipe into planned analyzer.py |

---

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...
```
