from __future__ import annotations
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .base import PostResult, LoginRequired, session_dir, screenshot_path
from ..config import Config

UPLOAD_URL = "https://studio.youtube.com/"

class YouTubePoster:
    name = "youtube"
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def post(self, clip_path, caption, *, profile="default", dry_run=False) -> PostResult:
        udd = session_dir(self.name, profile, profiles_root=self.cfg.profiles_dir)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(udd), headless=self.cfg.headless)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(UPLOAD_URL, wait_until="domcontentloaded")
                time.sleep(4)
                if "accounts.google.com" in page.url:
                    raise LoginRequired("redirigé vers login Google")
                page.get_by_role("button", name="Create").first.click(timeout=30000)
                page.get_by_text("Upload videos").first.click(timeout=30000)
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files(clip_path, timeout=30000)
                time.sleep(3)
                title = page.locator("#textbox").first
                title.wait_for(timeout=60000)
                title.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                title.type(caption[:95], delay=10)
                time.sleep(1)
                if dry_run:
                    shot = screenshot_path(self.name, "dryrun", logs_root=self.cfg.logs_dir)
                    page.screenshot(path=shot)
                    return PostResult(ok=True, url=None, screenshot=shot)
                for _ in range(3):
                    page.get_by_role("button", name="Next").first.click(timeout=30000)
                    time.sleep(1)
                page.get_by_role("radio", name="Public").first.click(timeout=30000)
                page.get_by_role("button", name="Publish").first.click(timeout=30000)
                time.sleep(8)
                return PostResult(ok=True, url="https://studio.youtube.com/")
            except LoginRequired:
                raise
            except PWTimeout as e:
                shot = screenshot_path(self.name, "error", logs_root=self.cfg.logs_dir)
                try: page.screenshot(path=shot)
                except Exception: shot = None
                return PostResult(ok=False, error=f"timeout: {e}", screenshot=shot)
            finally:
                ctx.close()
