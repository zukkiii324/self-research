from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "build_publish_site.py"
CHROME_PATH = Path(
    "/Users/kazuki/Library/Caches/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-mac-arm64/chrome-headless-shell"
)
SPEC = importlib.util.spec_from_file_location("build_publish_site", MODULE_PATH)
assert SPEC and SPEC.loader
publish_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publish_site
SPEC.loader.exec_module(publish_site)


class PublishSiteRenderTest(unittest.TestCase):
    @unittest.skipUnless(CHROME_PATH.exists(), "headless chrome not available")
    def test_mobile_render_does_not_overflow_key_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            content_root = base / "content"
            out_root = base / "publish_site"
            config_root = base / "config"
            shutil.copytree(PROJECT_ROOT / "content", content_root)
            config_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / "config" / "topic_catalog.json", config_root / "topic_catalog.json")
            current_dir = os.getcwd()
            try:
                os.chdir(base)
                publish_site.main()
            finally:
                os.chdir(current_dir)

            harness = out_root / "render-check.html"
            harness.write_text(
                textwrap.dedent(
                    """
                    <!doctype html>
                    <html lang="ja">
                    <body>
                      <pre id="result">pending</pre>
                      <script>
                        const pages = ["./index.html", "./ai_practical/index.html", "./baby/index.html", "./claude/index.html", "./industry_dx_ai_watch/index.html"];
                        const viewportWidth = 390;
                        async function inspectPage(path) {
                          return new Promise((resolve) => {
                            const iframe = document.createElement("iframe");
                            iframe.style.width = viewportWidth + "px";
                            iframe.style.height = "1200px";
                            iframe.style.border = "0";
                            iframe.src = path;
                            iframe.onload = () => {
                              const doc = iframe.contentDocument;
                              const win = iframe.contentWindow;
                              const root = doc.documentElement;
                              const body = doc.body;
                              const selectors = [".top-links", ".page-layout", ".hero-grid", ".article-card", ".panel"];
                              const selectorWidths = selectors.map((selector) => {
                                const node = doc.querySelector(selector);
                                return node ? Math.ceil(node.getBoundingClientRect().width) : 0;
                              });
                              const overflow = Math.max(root.scrollWidth, body.scrollWidth) - win.innerWidth;
                              resolve({
                                path,
                                innerWidth: win.innerWidth,
                                scrollWidth: Math.max(root.scrollWidth, body.scrollWidth),
                                overflow,
                                selectorWidths,
                              });
                              iframe.remove();
                            };
                            document.body.appendChild(iframe);
                          });
                        }
                        (async () => {
                          const results = [];
                          for (const page of pages) {
                            results.push(await inspectPage(page));
                          }
                          const failed = results.filter((item) => item.overflow > 2);
                          document.getElementById("result").textContent = JSON.stringify({results, failed}, null, 2);
                        })();
                      </script>
                    </body>
                    </html>
                    """
                ).strip(),
                encoding="utf-8",
            )

            try:
                result = subprocess.run(
                    [
                        str(CHROME_PATH),
                        "--headless=new",
                        "--allow-file-access-from-files",
                        "--dump-dom",
                        "--virtual-time-budget=45000",
                        "--window-size=430,1300",
                        harness.resolve().as_uri(),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as error:
                self.skipTest(f"headless chrome render check is not available in this environment: {error}")
            html = result.stdout
            html = result.stdout
            start = html.find("{")
            end = html.rfind("}")
            self.assertNotEqual(start, -1, "render-check result was not found in DOM")
            payload = json.loads(html[start:end + 1])
            self.assertEqual(payload["failed"], [], msg=json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    unittest.main()
