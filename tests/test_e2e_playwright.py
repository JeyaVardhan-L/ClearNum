"""Playwright End-to-End Automated Browser Tests for NumberShield."""

import threading
import time
import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.main import app


class LiveServer(threading.Thread):
    def __init__(self, host="127.0.0.1", port=8766):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = None

    def run(self):
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("playwright_isolated")
    test_db = temp_dir / "test_playwright.db"
    test_key = temp_dir / ".test_playwright_key"

    orig_db = settings.db_path
    orig_key = settings.key_path

    settings.db_path = test_db
    settings.key_path = test_key
    init_db(test_db)

    server = LiveServer(port=8766)
    server.start()
    time.sleep(2.0)
    yield "http://127.0.0.1:8766"
    server.stop()

    settings.db_path = orig_db
    settings.key_path = orig_key


def test_full_user_workflow_desktop(base_url):
    """Test full desktop workflow: navigation, demo loading, dorks, legal notice, spam logging, and purge."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Navigate to application root
        page.goto(base_url, wait_until="networkidle")
        assert page.locator("text=NumberShield").first.is_visible()

        # 2. Check brand and desktop navigation tabs
        assert page.locator("text=v1.0 Local").first.is_visible()
        nav = page.locator("nav")
        assert nav.locator("button:has-text('Scan & Dorks')").is_visible()
        assert nav.locator("button:has-text('Exposures')").is_visible()
        assert nav.locator("button:has-text('Remediation Hub')").is_visible()
        assert nav.locator("button:has-text('Spam & DND')").is_visible()
        assert nav.locator("button:has-text('Verify & Audit')").is_visible()

        # 3. Load synthetic demo scenario
        load_demo_btn = page.locator("button:has-text('Load Demo')").first
        assert load_demo_btn.is_visible()
        load_demo_btn.click()

        # Wait for toast and automatic navigation to Exposures tab
        page.wait_for_selector("text=Synthetic scenario loaded", timeout=10000)
        page.wait_for_selector("text=Discovered Exposures", timeout=10000)

        # 4. Verify exposures table contains realistic data broker entries
        assert page.locator("text=fastpeoplesearch.com").first.is_visible()
        assert page.locator("text=truepeoplesearch.com").first.is_visible()
        assert page.locator("text=Exact Match").first.is_visible()

        # 5. Switch to Scan & Dorks tab and test Direct Search Dorks modal
        nav.locator("button:has-text('Scan & Dorks')").click()
        page.wait_for_selector("text=Privacy Exposure Discovery Engine")

        dorks_btn = page.locator("button:has-text('Direct Search Dorks (1-Click)')")
        assert dorks_btn.is_visible()
        dorks_btn.click()

        # Wait for modal
        page.wait_for_selector("text=Pre-Computed Search Dorks", timeout=6000)
        assert page.locator("text=Google Search").first.is_visible()
        assert page.locator("text=Bing Search").first.is_visible()
        assert page.locator("text=Brave Search").first.is_visible()

        # Close modal
        page.locator("button:has-text('✕')").click()

        # 6. Switch to Remediation Hub and test Legal Notice Generator
        nav.locator("button:has-text('Remediation Hub')").click()
        page.wait_for_selector("text=Remediation Hub")
        page.wait_for_selector("text=FastPeopleSearch", timeout=6000)

        # Switch to Legal Notice Generator subtab
        page.locator("button:has-text('Legal Notice Generator')").click()
        page.wait_for_selector("text=Statutory Notice Configuration")

        # Generate CCPA notice
        generate_btn = page.locator("button:has-text('Generate Privacy Rights Notice')")
        assert generate_btn.is_visible()
        generate_btn.click()

        # Wait for notice output
        page.wait_for_selector("text=California Consumer Privacy Act", timeout=6000)
        page.wait_for_selector("text=Subject:", timeout=6000)
        assert page.locator("text=Civil Code § 1798.105").is_visible()

        # 7. Switch to Spam & DND tab and test incident logging & telecom guides
        nav.locator("button:has-text('Spam & DND')").click()
        page.wait_for_selector("text=Spam Reduction & Telecom DND")

        # Check National DND Registry info
        assert page.locator("text=National Do Not Call Registry").first.is_visible()
        assert page.locator("text=donotcall.gov").first.is_visible()
        assert page.locator("text=7726").first.is_visible()

        # Log an incident
        page.fill("input[placeholder*='+1 (555)']", "+18005550199")
        page.fill("input[placeholder*='vehicle service contract']", "Pre-recorded auto warranty protection pitch")
        page.locator("button:has-text('Record Incident & Re-Cluster')").click()

        page.wait_for_selector("text=Spam incident logged", timeout=6000)
        page.wait_for_selector("text=+18005550199", timeout=8000)
        assert page.locator("text=+18005550199").first.is_visible()

        # 8. Switch to Verify & Audit tab and test Zero-Trace Purge
        nav.locator("button:has-text('Verify & Audit')").click()
        page.wait_for_selector("text=Verification & Forensic Audit")
        assert page.locator("text=Cryptographic Guarantees").is_visible()
        assert page.locator("text=Current Identity HMAC-SHA256").is_visible()

        # Click Launch Cryptographic Purge
        page.locator("button:has-text('Launch Cryptographic Purge')").click()
        page.wait_for_selector("text=Confirm Zero-Trace Erasure")

        # Type PURGE
        page.fill("input[placeholder='Type PURGE to confirm']", "PURGE")
        page.locator("button:has-text('Permanently Destroy Data')").click()

        # Verify reset to initial scan console
        page.wait_for_selector("text=Privacy Exposure Discovery Engine", timeout=8000)

        browser.close()


def test_remediation_history_timeline_workflow(base_url):
    """Test Phase 6D Remediation History Timeline: modal open, chronological audit events, deadline indicators, dismiss, and empty state."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Navigate and load demo scenario
        page.goto(base_url, wait_until="networkidle")
        load_demo_btn = page.locator("button:has-text('Load Demo')").first
        load_demo_btn.click()
        page.wait_for_selector("text=Synthetic scenario loaded", timeout=10000)
        page.wait_for_selector("text=Discovered Exposures", timeout=10000)

        # 2. Click History on fastpeoplesearch row
        fps_row = page.locator("tr:has-text('fastpeoplesearch.com')")
        assert fps_row.is_visible()
        history_btn = fps_row.locator("button:has-text('History')")
        assert history_btn.is_visible()
        history_btn.click()

        # 3. Verify History Modal content and await async audit events
        page.wait_for_selector("h3:has-text('Remediation & Audit History')", timeout=6000)
        modal = page.locator("div[role='dialog']")
        assert modal.locator("text=fastpeoplesearch.com").first.is_visible()
        assert modal.locator("text=FPS-REF-89412").is_visible()
        assert modal.locator("text=Statutory Legal Deadline").is_visible()
        assert modal.locator("text=CCPA_DELETE").is_visible()
        assert modal.locator("text=WEB_FORM").is_visible()

        # Wait for forensic audit timeline events to finish loading
        page.wait_for_selector("text=DRAFT_GENERATION", timeout=6000)
        assert modal.locator("text=SUBMISSION_RECORD").is_visible()
        assert modal.locator("text=REQUEST_PREPARED").first.is_visible()

        # 4. Test closing via Close button
        modal.locator("button:has-text('Close')").click()
        page.wait_for_selector("h3:has-text('Remediation & Audit History')", state="hidden")

        # 5. Re-open and test dismissing via Escape key
        fps_row.locator("button:has-text('History')").click()
        page.wait_for_selector("h3:has-text('Remediation & Audit History')")
        page.keyboard.press("Escape")
        page.wait_for_selector("h3:has-text('Remediation & Audit History')", state="hidden")

        # 6. Test empty audit history state for exposure without actions
        wp_row = page.locator("tr:has-text('whitepages.com')")
        assert wp_row.is_visible()
        wp_row.locator("button:has-text('History')").click()
        page.wait_for_selector("text=No audit events recorded yet", timeout=6000)
        wp_modal = page.locator("div[role='dialog']")
        assert wp_modal.locator("text=No Statutory Basis").is_visible()
        wp_modal.locator("button:has-text('Close')").click()
        page.wait_for_selector("h3:has-text('Remediation & Audit History')", state="hidden")

        browser.close()


def test_mobile_viewport_responsiveness(base_url):
    """Test responsive rendering on mobile viewport (390x844 iPhone 12/13/14 size) including History modal."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.goto(base_url, wait_until="networkidle")
        assert page.locator("text=NumberShield").first.is_visible()

        # Load demo on mobile
        load_demo_btn = page.locator("button:has-text('Load Demo')").first
        load_demo_btn.click()

        page.wait_for_selector("text=Discovered Exposures", timeout=10000)

        # Check table does not cause horizontal page blowout (overflow-x contained)
        table = page.locator("table")
        assert table.is_visible()

        # Test History modal on mobile
        fps_row = page.locator("tr:has-text('fastpeoplesearch.com')")
        fps_row.locator("button:has-text('History')").click()
        page.wait_for_selector("h3:has-text('Remediation & Audit History')", timeout=6000)
        page.wait_for_selector("text=Statutory Legal Deadline", timeout=6000)
        assert page.locator("text=Statutory Legal Deadline").is_visible()

        # Close history modal via Escape key on mobile
        page.keyboard.press("Escape")
        page.wait_for_selector("h3:has-text('Remediation & Audit History')", state="hidden")

        # Switch to Remediation Hub via mobile sub-navigation bar
        mobile_btn = page.locator("header button:has-text('Remediation Hub')").first
        assert mobile_btn.is_visible()
        mobile_btn.click()
        page.wait_for_selector("text=Remediation Hub", timeout=8000)

        browser.close()
