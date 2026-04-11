# TA Brief

Daily technical analysis briefing pipeline from **Notion -> SQLite -> Claude -> markdown brief**.

This project pulls new research pages from a Notion database, stores them locally, and turns them into a single daily brief with recent-history context.

## What it does
- Syncs new pages from a Notion database into `ta_brief.db`
- Converts page blocks into plain text research notes
- Generates a daily brief with Claude
- Saves each brief locally in `briefings/`

## Files
- `ta_brief.py` - CLI entrypoint for syncing and briefing
- `notion.py` - Notion fetch logic
- `prompt.py` - Claude system prompt and prompt builders
- `ta_brief.db` - local SQLite store for pages and briefs

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set these environment variables in `.env`:

```bash
ANTHROPIC_API_KEY=...
NOTION_API_KEY=...
NOTION_DATABASE_ID=...
```

## Commands

Sync new Notion pages:

```bash
.venv/bin/python ta_brief.py sync
```

Generate a daily brief from unprocessed pages:

```bash
.venv/bin/python ta_brief.py brief
```

## Output
- New pages are stored in `ta_brief.db`
- Generated briefs are written to `briefings/YYYY-MM-DD.md`

## Status
Personal research tool. Active prototype.
