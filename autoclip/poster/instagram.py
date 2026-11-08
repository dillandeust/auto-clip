from __future__ import annotations
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .base import PostResult, LoginRequired, session_dir, screenshot_path
from ..config import Config

HOME_URL = "https://www.instagram.com/"

class InstagramPoster:
    name = "instagram"
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def post(self, clip_path, caption, *, profile="default", dry_run=False) -> PostResult:
        udd = session_dir(self.name, profile, profiles_root=self.cfg.profiles_dir)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(udd), headless=self.cfg.headless)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(HOME_URL, wait_until="domcontentloaded")
                time.sleep(3)
                if "accounts/login" in page.url:
                    raise LoginRequired("redirigé vers login Instagram")
                page.get_by_role("link", name="New post").first.click(timeout=30000)
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files(clip_path, timeout=30000)
                time.sleep(3)
                for _ in range(2):
                    page.get_by_role("button", name="Next").first.click(timeout=30000)
                    time.sleep(2)
                cap = page.get_by_role("textbox").first
                cap.click()
                cap.type(caption, delay=20)
                time.sleep(1)
                if dry_run:
                    shot = screenshot_path(self.name, "dryrun", logs_root=self.cfg.logs_dir)
                    page.screenshot(path=shot)
                    return PostResult(ok=True, url=None, screenshot=shot)
                page.get_by_role("button", name="Share").first.click(timeout=30000)
                time.sleep(10)
                return PostResult(ok=True, url=HOME_URL)
            except LoginRequired:
                raise
            except PWTimeout as e:
                shot = screenshot_path(self.name, "error", logs_root=self.cfg.logs_dir)
                try: page.screenshot(path=shot)
                except Exception: shot = None
                return PostResult(ok=False, error=f"timeout: {e}", screenshot=shot)
            finally:
                ctx.close()
