#!/usr/bin/env python3
"""
Fetch a Sentry issue and its latest event, write to a Markdown file.
Usage: python scripts/fetch_sentry_issue.py <issue_id> [output.md]
Requires: SENTRY_AUTH_TOKEN in env (or .env). Optional: SENTRY_ORG (default: geeked-out-games).
"""
import os
import sys
import json
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE = "https://sentry.io/api/0"


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/fetch_sentry_issue.py <issue_id> [output.md]", file=sys.stderr)
        sys.exit(1)
    issue_id = sys.argv[1].strip()
    out_path = sys.argv[2] if len(sys.argv) > 2 else "docs/Sentry_Bug_Reports/Bug1.md"
    org = os.environ.get("SENTRY_ORG", "geeked-out-games")

    token = os.environ.get("SENTRY_AUTH_TOKEN")
    if not token:
        print("Set SENTRY_AUTH_TOKEN in .env or environment.", file=sys.stderr)
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # Get issue (org-scoped; required for many Sentry setups)
    r = requests.get(f"{BASE}/organizations/{org}/issues/{issue_id}/", headers=headers, timeout=15)
    if not r.ok:
        print(f"Issue fetch failed: {r.status_code} {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    issue = r.json()

    # Get latest event
    r2 = requests.get(f"{BASE}/organizations/{org}/issues/{issue_id}/events/latest/", headers=headers, timeout=15)
    event = r2.json() if r2.status_code == 200 else {}

    # Build markdown
    title = issue.get("title", "Unknown")
    culprit = issue.get("culprit", "")
    permalink = issue.get("permalink", "")
    md = [f"# {title}", ""]
    if permalink:
        md.append(f"**Link:** {permalink}")
        md.append("")
    if culprit:
        md.append(f"**Culprit:** `{culprit}`")
        md.append("")

    # Event: message and exception (Sentry can use different shapes)
    if event:
        msg = event.get("message") or (event.get("metadata", {}) or {}).get("value")
        if msg:
            md.append("## Message")
            md.append("")
            md.append(str(msg))
            md.append("")
        # Exception: top-level or under exception.values
        exc_list = event.get("exception", {}).get("values", []) if isinstance(event.get("exception"), dict) else []
        if not exc_list and isinstance(event.get("exception"), list):
            exc_list = event.get("exception", [])
        for exc in exc_list:
            if not isinstance(exc, dict):
                continue
            md.append("## Exception")
            md.append("")
            md.append(f"**{exc.get('type', 'Error')}:** {exc.get('value', '')}")
            md.append("")
            st = exc.get("stacktrace") or {}
            frames = st.get("frames", []) if isinstance(st, dict) else []
            if frames:
                md.append("```")
                for frame in frames:
                    fn = frame.get("filename", "?") or "?"
                    ln = frame.get("lineNo") or frame.get("line_no") or "?"
                    fn_short = fn.split("/")[-1] if "/" in str(fn) else fn
                    md.append(f"  {fn_short}:{ln}")
                md.append("```")
                md.append("")
        # Request
        req = (event.get("request", {}) or {})
        if req:
            md.append("## Request")
            md.append("")
            md.append(f"- **URL:** {req.get('url', '')}")
            md.append(f"- **Method:** {req.get('method', '')}")
            md.append("")
        # If we still have no exception block, show event keys so we can debug
        if not exc_list and event.get("metadata"):
            md.append("## Metadata")
            md.append("")
            md.append("```")
            md.append(json.dumps(event.get("metadata"), indent=2))
            md.append("```")
            md.append("")

    body = "\n".join(md)
    if not body.strip():
        body = f"# {title}\n\nNo event details returned. Check SENTRY_ORG (current: {org}) and issue ID."
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(body)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
