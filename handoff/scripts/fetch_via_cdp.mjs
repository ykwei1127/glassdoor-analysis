import { pathToFileURL } from "node:url";

async function loadPlaywright() {
  const explicitModule = process.env.PLAYWRIGHT_MODULE;
  if (explicitModule) {
    return import(pathToFileURL(explicitModule).href);
  }
  return import("playwright");
}

async function main() {
  const [, , cdpUrl, targetUrl] = process.argv;
  if (!cdpUrl || !targetUrl) {
    throw new Error("Usage: node fetch_via_cdp.mjs <cdp-url> <target-url>");
  }

  const { chromium } = await loadPlaywright();

  const browser = await chromium.connectOverCDP(cdpUrl);
  try {
    const contexts = browser.contexts();
    const context = contexts[0];
    if (!context) {
      throw new Error("No browser context available from CDP session.");
    }

    const page = await context.newPage();
    try {
      const response = await page.goto(targetUrl, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForTimeout(3000);
      const payload = {
        url: page.url(),
        status_code: response ? response.status() : 200,
        text: await page.content(),
      };
      process.stdout.write(JSON.stringify(payload));
    } finally {
      await page.close().catch(() => {});
    }
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.stack || error.message : String(error);
  process.stderr.write(message);
  process.exit(1);
});
