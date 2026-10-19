"""Visual transformation capture for MWU-CRUD-001.

Drives Playwright headless Chromium against both:
  - Legacy PHP app at http://php-legacy/
  - New React SPA at http://react-new/

Captures 8 legacy screens + 8 new-SPA states. Writes PNGs to /app/screenshots/
which is bind-mounted to migrations/crud/screenshots/.

Exit 0 on success; 1 if any capture failed.
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import Page, sync_playwright


PHP_URL = os.environ.get("PHP_REFERENCE_URL", "http://php-legacy")
REACT_URL = os.environ.get("REACT_TARGET_URL", "http://react-new")
OUT_DIR = os.environ.get("SCREENSHOT_DIR", "/app/screenshots")

LEGACY_SHOTS = [
    ("old-01-list.png",             "list"),
    ("old-02-add-form.png",         "add_form"),
    ("old-03-edit-form-id1.png",    "edit_form_id1"),
    ("old-04-edit-missing-id.png",  "edit_form_id999"),
    ("old-05-delete-hover.png",     "delete_hover"),
    ("old-06-add-action-success.png","add_action_then_list"),
    ("old-07-list-narrow.png",      "list_narrow"),
    ("old-08-edit-form-id2.png",    "edit_form_id2"),
]

NEW_SHOTS = [
    ("new-01-list.png",             "list"),
    ("new-02-add-modal.png",        "add_modal"),
    ("new-03-add-validation-error.png", "add_validation"),
    ("new-04-edit-modal.png",       "edit_modal"),
    ("new-05-edit-email-conflict.png", "edit_email_conflict"),
    ("new-06-delete-alert.png",     "delete_alert"),
    ("new-07-loading-skeleton.png", "loading_skeleton"),
    ("new-08-empty-state.png",      "empty_state"),
]


def shoot_legacy(page: Page, scenario: str, out_path: str) -> None:
    if scenario == "list":
        page.goto(f"{PHP_URL}/index.php", wait_until="networkidle", timeout=20_000)
    elif scenario == "add_form":
        page.goto(f"{PHP_URL}/add.php", wait_until="networkidle", timeout=20_000)
    elif scenario == "edit_form_id1":
        page.goto(f"{PHP_URL}/edit.php?id=1", wait_until="networkidle", timeout=20_000)
    elif scenario == "edit_form_id2":
        page.goto(f"{PHP_URL}/edit.php?id=2", wait_until="networkidle", timeout=20_000)
    elif scenario == "edit_form_id999":
        page.goto(f"{PHP_URL}/edit.php?id=999", wait_until="networkidle", timeout=20_000)
    elif scenario == "delete_hover":
        page.goto(f"{PHP_URL}/index.php", wait_until="networkidle", timeout=20_000)
        try:
            page.get_by_text("Delete").first.hover()
        except Exception:
            pass
    elif scenario == "add_action_then_list":
        # post a new row, then capture the redirected list
        page.goto(f"{PHP_URL}/add.php", wait_until="networkidle", timeout=20_000)
        page.locator('input[name="name"]').fill("Frank")
        page.locator('input[name="age"]').fill("33")
        page.locator('input[name="email"]').fill("frank@example.com")
        page.locator('input[type="submit"], button[type="submit"]').first.click()
        page.wait_for_load_state("networkidle", timeout=20_000)
    elif scenario == "list_narrow":
        page.set_viewport_size({"width": 420, "height": 800})
        page.goto(f"{PHP_URL}/index.php", wait_until="networkidle", timeout=20_000)
    page.screenshot(path=out_path, full_page=True)
    # restore standard viewport after narrow
    if scenario == "list_narrow":
        page.set_viewport_size({"width": 1280, "height": 800})


def shoot_new(page: Page, scenario: str, out_path: str) -> None:
    base = REACT_URL
    if scenario == "loading_skeleton":
        # Block the API so the skeleton state is visible.
        page.route("**/api/users**", lambda r: r.abort())
        page.goto(f"{base}/", wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(300)
        page.screenshot(path=out_path, full_page=True)
        page.unroute("**/api/users**")
        return
    if scenario == "empty_state":
        # Intercept list to return [].
        page.route(
            "**/api/users",
            lambda r: r.fulfill(status=200, content_type="application/json", body="[]"),
        )
        page.goto(f"{base}/", wait_until="networkidle", timeout=20_000)
        page.screenshot(path=out_path, full_page=True)
        page.unroute("**/api/users")
        return

    page.goto(f"{base}/", wait_until="networkidle", timeout=20_000)
    if scenario == "list":
        pass
    elif scenario == "add_modal":
        page.get_by_role("button", name="Add User").click()
        page.wait_for_timeout(300)
    elif scenario == "add_validation":
        page.get_by_role("button", name="Add User").click()
        page.wait_for_timeout(200)
        # Submit empty to trigger Zod errors
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(300)
    elif scenario == "edit_modal":
        page.locator('button[aria-label^="Edit"]').first.click()
        page.wait_for_timeout(300)
    elif scenario == "edit_email_conflict":
        page.locator('button[aria-label^="Edit"]').first.click()
        page.wait_for_timeout(200)
        # Type an already-used email (Bob's, seeded)
        email = page.locator('input[name="email"]')
        email.fill("bob@example.com")
        page.get_by_role("button", name="Update").click()
        page.wait_for_timeout(500)
    elif scenario == "delete_alert":
        page.locator('button[aria-label^="Delete"]').first.click()
        page.wait_for_timeout(300)
    page.screenshot(path=out_path, full_page=True)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()

        for fname, scenario in LEGACY_SHOTS:
            out = os.path.join(OUT_DIR, fname)
            try:
                shoot_legacy(page, scenario, out)
                print(f"[screenshot] {out}")
            except Exception as exc:
                errors.append(f"{fname}: {exc}")
                print(f"[screenshot] FAIL {fname}: {exc}", file=sys.stderr)

        for fname, scenario in NEW_SHOTS:
            out = os.path.join(OUT_DIR, fname)
            try:
                shoot_new(page, scenario, out)
                print(f"[screenshot] {out}")
            except Exception as exc:
                errors.append(f"{fname}: {exc}")
                print(f"[screenshot] FAIL {fname}: {exc}", file=sys.stderr)

        browser.close()

    total = len(LEGACY_SHOTS) + len(NEW_SHOTS)
    if errors:
        print(f"\n[screenshot] {len(errors)}/{total} failure(s)", file=sys.stderr)
        return 1
    print(f"\n[screenshot] all {total} captured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
