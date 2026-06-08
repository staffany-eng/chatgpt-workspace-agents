#!/usr/bin/env python3
"""
Launchbot help article screenshot runner.
Reads a screenshot plan JSON and captures screenshots via Playwright.

Usage:
  python3 help-article-screenshot-runner.py \
    --plan apps/launchbot/output/help-articles/screenshot-plans/<slug>.json \
    --source-url https://staging.staffany.com \
    --storage-state /tmp/launchbot-staging-storage-state.json \
    --output-dir apps/launchbot/output/help-articles/assets/<slug>

  # Dry run (no capture):
  python3 help-article-screenshot-runner.py --plan <plan.json> --dry-run --output-dir <dir>
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--source-url', default=os.environ.get('LAUNCHBOT_STAGING_URL', ''))
    parser.add_argument('--storage-state', default='')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout-ms', type=int, default=30000)
    parser.add_argument('--allow-blocked', action='store_true')
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"Plan not found: {args.plan}", file=sys.stderr)
        sys.exit(1)

    with open(plan_path) as f:
        plan = json.load(f)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "article_slug": plan.get("article_slug"),
        "article_title": plan.get("article_title"),
        "jira_key": plan.get("jira_key"),
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "dry_run": args.dry_run,
        "source_url": args.source_url,
        "status": "pending",
        "blocker": None,
        "shots": []
    }

    if args.dry_run:
        print(f"DRY RUN — plan: {args.plan}")
        print(f"Source URL: {args.source_url or '(not set)'}")
        print(f"Storage state: {args.storage_state or '(not set)'}")
        print(f"Output dir: {args.output_dir}")
        print(f"Shots to capture ({len(plan['shots'])}):")
        for shot in plan["shots"]:
            print(f"  [{shot['id']}] {shot['label']} — route: {shot.get('route', 'N/A')}")
            manifest["shots"].append({
                "id": shot["id"],
                "label": shot["label"],
                "status": "dry_run",
                "route": shot.get("route"),
                "waitForText": shot.get("wait_for_text"),
                "file": None
            })
        manifest["status"] = "dry_run"
        manifest_path = output_dir / "screenshot-manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nManifest saved: {manifest_path}")
        return

    # Real capture
    if not args.source_url:
        print("blocked: missing LAUNCHBOT_STAGING_URL / --source-url", file=sys.stderr)
        manifest["status"] = "blocked"
        manifest["blocker"] = "missing_source_url"
        save_manifest(manifest, output_dir)
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("blocked: playwright_not_installed", file=sys.stderr)
        manifest["status"] = "blocked"
        manifest["blocker"] = "playwright_not_installed"
        save_manifest(manifest, output_dir)
        sys.exit(1)

    storage_state = args.storage_state if args.storage_state and Path(args.storage_state).exists() else None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()

        for shot in plan["shots"]:
            shot_result = {
                "id": shot["id"],
                "label": shot["label"],
                "status": "pending",
                "route": shot.get("route"),
                "waitForText": shot.get("wait_for_text"),
                "file": None,
                "blocker": None
            }

            if shot.get("trigger_note") and not shot.get("route"):
                shot_result["status"] = "skipped"
                shot_result["blocker"] = f"requires_manual_trigger: {shot.get('trigger_note', '')}"
                manifest["shots"].append(shot_result)
                print(f"  SKIP [{shot['id']}] — {shot_result['blocker']}")
                continue

            try:
                url = args.source_url.rstrip('/') + shot['route']
                print(f"  Navigating to {url} ...")
                page.goto(url, wait_until='networkidle', timeout=args.timeout_ms)

                if shot.get("wait_for_text"):
                    page.wait_for_selector(f"text={shot['wait_for_text']}", timeout=args.timeout_ms)

                if shot.get("wait_for_selector"):
                    page.wait_for_selector(shot["wait_for_selector"], timeout=args.timeout_ms)

                # Redact
                for selector in shot.get("redact_selectors", []):
                    try:
                        page.eval_on_selector_all(selector,
                            "els => els.forEach(el => { el.style.filter='blur(8px)'; el.setAttribute('aria-hidden','true') })")
                    except Exception:
                        pass

                filename = f"{shot['id']}.png"
                filepath = output_dir / filename

                clip = None
                if shot.get("clip_selector"):
                    try:
                        bbox = page.locator(shot["clip_selector"]).first.bounding_box()
                        if bbox:
                            clip = {"x": bbox["x"], "y": bbox["y"],
                                    "width": bbox["width"], "height": bbox["height"]}
                    except Exception:
                        pass

                page.screenshot(path=str(filepath), full_page=False, clip=clip)
                shot_result["status"] = "captured"
                shot_result["file"] = filename
                print(f"  OK  [{shot['id']}] → {filename}")

            except Exception as e:
                shot_result["status"] = "blocked"
                shot_result["blocker"] = str(e)
                print(f"  ERR [{shot['id']}] — {e}")
                if not args.allow_blocked:
                    manifest["shots"].append(shot_result)
                    manifest["status"] = "blocked"
                    manifest["blocker"] = f"shot_{shot['id']}_failed"
                    save_manifest(manifest, output_dir)
                    browser.close()
                    sys.exit(1)

            manifest["shots"].append(shot_result)

        browser.close()

    all_ok = all(s["status"] in ("captured", "skipped", "dry_run") for s in manifest["shots"])
    manifest["status"] = "complete" if all_ok else "partial"
    save_manifest(manifest, output_dir)
    print(f"\nManifest saved: {output_dir / 'screenshot-manifest.json'}")
    print(f"Status: {manifest['status']}")

def save_manifest(manifest, output_dir):
    path = Path(output_dir) / "screenshot-manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    main()
