#!/usr/bin/env python3
import argparse
import os
import sqlite3
import time
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

import notion as notion_client
from prompt import SYSTEM_PROMPT, build_brief_prompt, build_summarize_prompt

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "ta_brief.db")
BRIEFINGS_DIR = os.path.join(os.path.dirname(__file__), "briefings")
LARGE_CONTENT_THRESHOLD = 150_000  # chars — above this, summarize per article first
PRIOR_BRIEF_COUNT = 3


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            id           INTEGER PRIMARY KEY,
            notion_id    TEXT UNIQUE NOT NULL,
            title        TEXT,
            content      TEXT,
            fetched_at   TEXT,
            processed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS briefs (
            id         INTEGER PRIMARY KEY,
            date       TEXT,
            filepath   TEXT,
            content    TEXT,
            created_at TEXT
        );
    """)
    conn.commit()


# ── Claude helpers ─────────────────────────────────────────────────────────────

def call_claude(model, system, user_message, max_retries=5):
    client = anthropic.Anthropic()
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except anthropic.RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"Rate limited. Retrying in {wait}s...")
            time.sleep(wait)


def summarize_article(title, content):
    print(f"  Summarizing: {title}")
    return call_claude(
        model="claude-haiku-4-5-20251001",
        system="You are a concise technical analysis research assistant.",
        user_message=build_summarize_prompt(title, content),
    )


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_sync(conn):
    """Fetch net-new pages from Notion and store in SQLite."""
    print("Fetching new pages from Notion...")
    new_pages = notion_client.fetch_new_pages(conn)

    if not new_pages:
        print("No new pages found.")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    for page in new_pages:
        conn.execute(
            "INSERT OR IGNORE INTO pages (notion_id, title, content, fetched_at) VALUES (?, ?, ?, ?)",
            (page["notion_id"], page["title"], page["content"], now),
        )
    conn.commit()
    print(f"Synced {len(new_pages)} new page(s).")
    return len(new_pages)


def cmd_brief(conn):
    """Generate a TA brief from all unprocessed pages."""
    rows = conn.execute(
        "SELECT id, notion_id, title, content FROM pages WHERE processed_at IS NULL"
    ).fetchall()

    if not rows:
        print("No unprocessed pages. Run 'sync' first or add articles to Notion.")
        return

    print(f"Generating brief from {len(rows)} page(s)...")

    # Build articles text — summarize per article if total is large
    total_chars = sum(len(r["content"] or "") for r in rows)
    article_sections = []

    if total_chars >= LARGE_CONTENT_THRESHOLD:
        print(f"Large content detected ({total_chars:,} chars). Summarizing per article first...")
        for row in rows:
            summary = summarize_article(row["title"], row["content"])
            article_sections.append(f"### {row['title']}\n{summary}")
    else:
        for row in rows:
            article_sections.append(f"### {row['title']}\n{row['content']}")

    articles_text = "\n\n---\n\n".join(article_sections)

    # Load prior briefs for historical context
    prior_rows = conn.execute(
        "SELECT date, content FROM briefs ORDER BY created_at DESC LIMIT ?",
        (PRIOR_BRIEF_COUNT,),
    ).fetchall()
    prior_briefs = [{"date": r["date"], "content": r["content"]} for r in prior_rows]

    # Generate brief
    print("Calling Claude for brief generation...")
    user_message = build_brief_prompt(articles_text, prior_briefs)
    brief_content = call_claude(
        model="claude-opus-4-6",
        system=SYSTEM_PROMPT,
        user_message=user_message,
    )

    # Save markdown file
    os.makedirs(BRIEFINGS_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(BRIEFINGS_DIR, f"{today}.md")

    header = f"# TA Brief — {today}\n\n"
    with open(filepath, "w") as f:
        f.write(header + brief_content)

    # Persist brief to SQLite
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO briefs (date, filepath, content, created_at) VALUES (?, ?, ?, ?)",
        (today, filepath, brief_content, now),
    )

    # Mark pages as processed
    page_ids = [r["id"] for r in rows]
    conn.execute(
        f"UPDATE pages SET processed_at = ? WHERE id IN ({','.join('?' * len(page_ids))})",
        [now] + page_ids,
    )
    conn.commit()

    print(f"Brief saved to: {filepath}")


def cmd_run(conn):
    """Sync new Notion pages then generate a brief."""
    synced = cmd_sync(conn)
    if synced == 0:
        # Check if there are existing unprocessed pages from a prior sync
        unprocessed = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE processed_at IS NULL"
        ).fetchone()[0]
        if unprocessed == 0:
            print("Nothing to brief. Add articles to your Notion database and try again.")
            return
    cmd_brief(conn)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ta-brief: generate TA briefs from Notion articles and transcripts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Sync Notion pages and generate brief (default)")
    subparsers.add_parser("sync", help="Fetch new Notion pages only")
    subparsers.add_parser("brief", help="Generate brief from already-synced pages")

    args = parser.parse_args()

    conn = get_db()
    init_db(conn)

    if args.command == "run":
        cmd_run(conn)
    elif args.command == "sync":
        cmd_sync(conn)
    elif args.command == "brief":
        cmd_brief(conn)

    conn.close()


if __name__ == "__main__":
    main()
