import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client():
    global _client
    if _client is None:
        _client = Client(auth=os.environ["NOTION_API_KEY"])
    return _client


def fetch_new_pages(db_conn):
    """Fetch all pages from Notion DB, return only those not yet in local SQLite."""
    client = get_client()
    database_id = os.environ["NOTION_DATABASE_ID"]

    known_ids = {
        row[0]
        for row in db_conn.execute("SELECT notion_id FROM pages").fetchall()
    }

    new_pages = []
    cursor = None

    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor

        response = client.databases.query(**kwargs)

        for page in response["results"]:
            notion_id = page["id"]
            if notion_id not in known_ids:
                title = get_page_title(page)
                content = fetch_page_content(notion_id)
                new_pages.append({
                    "notion_id": notion_id,
                    "title": title,
                    "content": content,
                })

        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]

    return new_pages


def get_page_title(page):
    """Extract the title from a Notion page's properties."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(t.get("plain_text", "") for t in title_parts)
    return "Untitled"


def fetch_page_content(page_id):
    """Fetch all blocks for a page and convert to plain text."""
    client = get_client()
    blocks = []
    cursor = None

    while True:
        kwargs = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor

        response = client.blocks.children.list(**kwargs)
        blocks.extend(response["results"])

        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]

    return blocks_to_text(blocks)


def blocks_to_text(blocks):
    """Convert Notion blocks to clean plain text."""
    lines = []

    for block in blocks:
        block_type = block.get("type")
        data = block.get(block_type, {})
        rich_text = data.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich_text)

        if not text.strip() and block_type not in ("divider",):
            continue

        if block_type == "heading_1":
            lines.append(f"# {text}")
        elif block_type == "heading_2":
            lines.append(f"## {text}")
        elif block_type == "heading_3":
            lines.append(f"### {text}")
        elif block_type in ("bulleted_list_item", "numbered_list_item"):
            lines.append(f"- {text}")
        elif block_type == "to_do":
            checked = data.get("checked", False)
            lines.append(f"[{'x' if checked else ' '}] {text}")
        elif block_type == "quote":
            lines.append(f"> {text}")
        elif block_type == "divider":
            lines.append("---")
        elif block_type == "code":
            lines.append(f"```\n{text}\n```")
        elif block_type == "paragraph":
            lines.append(text)
        # skip unsupported block types (image, embed, etc.)

    return "\n".join(lines)
