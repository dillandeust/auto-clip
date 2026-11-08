from __future__ import annotations
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .base import PostResult, LoginRequired, session_dir, screenshot_path
from ..config import Config

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"

class TikTokPoster:
    name = "tiktok"
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def post(self, clip_path, caption, *, profile="default", dry_run=False) -> PostResult:
        udd = session_dir(self.name, profile, profiles_root=self.cfg.profiles_dir)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(udd), headless=self.cfg.headless)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(UPLOAD_URL, wait_until="domcontentloaded")
                time.sleep(3)
                if "login" in page.url:
                    raise LoginRequired("redirigé vers login TikTok")
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files(clip_path, timeout=30000)
                cap = page.locator("div[contenteditable='true']").first
                cap.wait_for(timeout=60000)
                cap.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                cap.type(caption, delay=20)
                time.sleep(2)
                if dry_run:
                    shot = screenshot_path(self.name, "dryrun", logs_root=self.cfg.logs_dir)
                    page.screenshot(path=shot)
                    return PostResult(ok=True, url=None, screenshot=shot)
                page.get_by_role("button", name="Post").first.click(timeout=30000)
                page.wait_for_url("**/content**", timeout=120000)
                return PostResult(ok=True, url=page.url)
            except LoginRequired:
                raise
            except PWTimeout as e:
                shot = screenshot_path(self.name, "error", logs_root=self.cfg.logs_dir)
                try: page.screenshot(path=shot)
                except Exception: shot = None
                return PostResult(ok=False, error=f"timeout: {e}", screenshot=shot)
            finally:
                ctx.close()
