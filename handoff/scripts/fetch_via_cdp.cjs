async function loadPlaywright() {
  const explicitModule = process.env.PLAYWRIGHT_MODULE;
  if (explicitModule) {
    return require(explicitModule);
  }
  return require("playwright");
}

async function main() {
  const [, , cdpUrl, targetUrl] = process.argv;
  if (!cdpUrl || !targetUrl) {
    throw new Error("Usage: node fetch_via_cdp.cjs <cdp-url> <target-url>");
  }

  const { chromium } = await loadPlaywright();
  const browser = await chromium.connectOverCDP(cdpUrl);
  try {
    const contexts = browser.contexts();
    const context = contexts[0];
    if (!context) {
      throw new Error("No browser context available from CDP session.");
    }

    const normalizedTargetUrl = new URL(targetUrl);
    normalizedTargetUrl.hash = "";
    const existingPage = context.pages().find((candidate) => {
      try {
        const candidateUrl = new URL(candidate.url());
        candidateUrl.hash = "";
        return candidateUrl.href === normalizedTargetUrl.href;
      } catch {
        return false;
      }
    });
    const page = existingPage || await context.newPage();
    const ownsPage = !existingPage;
    try {
      const response = ownsPage
        ? await page.goto(targetUrl, {
            waitUntil: "domcontentloaded",
            timeout: 15000,
          })
        : null;
      if (/\/Location\/All-.*-Office-Locations-E\d+\.htm(?:[?#]|$)/i.test(targetUrl)) {
        await page.waitForSelector('[data-test="location-row"]', { timeout: 7000 }).catch(() => {});
      }
      await page.waitForTimeout(1000);
      const payload = {
        url: page.url(),
        status_code: response ? response.status() : 200,
        text: await page.content(),
      };
      process.stdout.write(JSON.stringify(payload));
    } finally {
      if (ownsPage) {
        await page.close().catch(() => {});
      }
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
