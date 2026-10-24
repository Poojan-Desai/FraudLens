import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright-core";

const token = process.env.FRAUDLENS_DEMO_ANALYST_TOKEN;
assert.ok(token, "Source the ignored local demo environment before running");
const baseURL = process.env.FRAUDLENS_BROWSER_URL ?? "http://127.0.0.1:4176";
const output =
  process.env.FRAUDLENS_BROWSER_OUTPUT ?? "work/investigation-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  ...(process.env.FRAUDLENS_BROWSER_EXECUTABLE
    ? { executablePath: process.env.FRAUDLENS_BROWSER_EXECUTABLE }
    : { channel: "chrome" }),
  headless: true,
});
const results = [];
const check = (name, condition) => {
  assert.ok(condition, name);
  results.push({ name, passed: true });
};
const errors = [];
async function connect(page) {
  await page.goto(`${baseURL}/investigations/`, { waitUntil: "networkidle" });
  await page.getByLabel("Case access token", { exact: true }).fill(token);
  await page
    .getByRole("button", { name: "Connect case store", exact: true })
    .click();
  await page.getByRole("region", { name: "Case queue", exact: true }).waitFor();
}
try {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`${baseURL}/investigations/`, { waitUntil: "networkidle" });
    await page
      .getByLabel("Case access token", { exact: true })
      .fill("invalid-credential-".repeat(3));
    await page
      .getByRole("button", { name: "Connect case store", exact: true })
      .click();
    await page.locator(".investigation-error").waitFor();
    check(
      `${width}: invalid credentials fail without case data`,
      (await page
        .getByRole("region", { name: "Case queue", exact: true })
        .count()) === 0,
    );
    await page.getByLabel("Case access token", { exact: true }).fill(token);
    await page
      .getByRole("button", { name: "Connect case store", exact: true })
      .click();
    await page
      .getByRole("region", { name: "Case queue", exact: true })
      .waitFor();
    check(
      `${width}: real saved cases load`,
      (await page.locator(".investigation-queue li").count()) > 0,
    );
    check(
      `${width}: credentials are absent from persistent browser storage`,
      await page.evaluate(
        () => localStorage.length === 0 && sessionStorage.length === 0,
      ),
    );
    await page
      .locator(".investigation-queue li button")
      .filter({ hasText: /pending · v1/ })
      .first()
      .click();
    await page
      .getByRole("button", { name: "Mark reviewed", exact: true })
      .waitFor();
    const id = await page.locator(".investigation-detail h2").innerText();
    check(
      `${width}: saved model provenance and score render`,
      (await page.locator(".case-model").innerText()).includes(
        "verified synthetic study",
      ) && (await page.locator(".case-facts").innerText()).includes("verified"),
    );
    // A second page reads the same version before the first writer acts.
    const stale = await context.newPage();
    stale.on("pageerror", (error) => errors.push(error.message));
    await connect(stale);
    await stale
      .getByLabel("Search case transaction ID", { exact: true })
      .fill(id);
    await stale
      .getByRole("button", { name: "Search cases", exact: true })
      .click();
    await stale.waitForFunction(
      () => document.querySelectorAll(".investigation-queue li").length === 1,
    );
    await stale.locator(".investigation-queue li button").first().click();
    await stale
      .getByRole("button", { name: "Mark reviewed", exact: true })
      .waitFor();
    const untrusted =
      '<img src=x onerror="window.caseXss=true"> Synthetic evidence reviewed.';
    await page.getByLabel("Investigator note", { exact: true }).fill(untrusted);
    await page.getByRole("button", { name: "Add note", exact: true }).click();
    await page
      .getByText("Saved version 2; action history verified.", { exact: true })
      .waitFor();
    check(
      `${width}: note is rendered as plain text`,
      (await page
        .locator(".case-history")
        .innerText()
        .then((text) => text.includes(untrusted))) &&
        (await page.evaluate(() => !window.caseXss)) &&
        (await page.locator(".case-history img").count()) === 0,
    );
    await stale
      .getByLabel("Investigator note", { exact: true })
      .fill("Stale analyst evidence must be retained.");
    await stale
      .getByRole("button", { name: "Mark reviewed", exact: true })
      .click();
    await stale.locator(".investigation-error").waitFor();
    check(
      `${width}: stale writer sees explicit conflict`,
      (await stale.locator(".investigation-error").innerText()).includes(
        "Case changed",
      ),
    );
    check(
      `${width}: stale note is retained`,
      (await stale
        .getByLabel("Investigator note", { exact: true })
        .inputValue()) === "Stale analyst evidence must be retained.",
    );
    await stale
      .getByRole("button", { name: "Reload case", exact: true })
      .click();
    await stale.waitForFunction(() =>
      document
        .querySelector(".investigation-detail .section-label")
        .textContent.includes("version 2"),
    );
    check(
      `${width}: reload preserves unsaved note`,
      (await stale
        .getByLabel("Investigator note", { exact: true })
        .inputValue()) === "Stale analyst evidence must be retained.",
    );
    await stale
      .getByRole("button", { name: "Mark reviewed", exact: true })
      .click();
    await stale
      .getByText("Saved version 3; action history verified.", { exact: true })
      .waitFor();
    await stale.close();
    await page
      .getByRole("button", { name: "Reload case", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Mark legitimate", exact: true })
      .waitFor();
    await page
      .getByLabel("Investigator note", { exact: true })
      .fill("Synthetic manual review outcome; not a trusted training label.");
    await page
      .getByRole("button", { name: "Mark legitimate", exact: true })
      .click();
    await page
      .getByText("Saved version 4; action history verified.", { exact: true })
      .waitFor();
    check(
      `${width}: resolution records four auditable events`,
      (await page.locator(".case-history li").count()) === 4,
    );
    check(
      `${width}: analyst cannot reopen terminal decision`,
      (await page
        .getByRole("button", { name: "Mark reviewed", exact: true })
        .count()) === 0,
    );
    const downloadPromise = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Export sanitized report", exact: true })
      .click();
    const download = await downloadPromise;
    await download.saveAs(`${output}/case-report-${width}.json`);
    const report = await (
      await import("node:fs/promises")
    ).readFile(`${output}/case-report-${width}.json`, "utf8");
    const parsed = JSON.parse(report);
    check(
      `${width}: report is real, sanitized and label-ineligible`,
      parsed.case.transaction_id === id &&
        parsed.sanitized &&
        parsed.case.training_label_eligible === false &&
        !report.includes(untrusted) &&
        !report.includes("demo-analyst"),
    );
    const size = await page.evaluate(() => ({
      width: innerWidth,
      body: document.body.scrollWidth,
      document: document.documentElement.scrollWidth,
    }));
    check(
      `${width}: no horizontal page overflow`,
      size.body <= width + 1 && size.document <= width + 1,
    );
    await page.screenshot({
      path: `${output}/investigations-${width}.png`,
      fullPage: true,
    });
    await page.reload({ waitUntil: "networkidle" });
    check(
      `${width}: reload clears credential and requires authentication`,
      (await page
        .getByLabel("Case access token", { exact: true })
        .inputValue()) === "" &&
        (await page
          .getByRole("region", { name: "Case queue", exact: true })
          .count()) === 0,
    );
    await context.close();
  }
  check("no investigation browser exceptions", errors.length === 0);
  console.log(`${results.length} investigation browser checks passed`);
} finally {
  await writeFile(
    `${output}/results.json`,
    JSON.stringify(
      { baseURL, checks: results, browserErrors: errors },
      null,
      2,
    ),
  );
  await browser.close();
}
