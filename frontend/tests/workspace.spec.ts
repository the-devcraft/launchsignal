import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

const captures = path.resolve(__dirname, "../../docs/screenshots");
async function signIn(page: Page) {
  await page.goto("/");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.DEMO_PASSWORD || "");
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Make the next move count." }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Orbit Studio" });
  await page
    .getByRole("combobox", { name: "Website", exact: true })
    .selectOption({ label: "Orbit Studio" });
  await expect(
    page.getByRole("heading", { name: "Describe meaningful images" }),
  ).toBeVisible();
}

test("real dashboard, billing and activity screenshots; accessible desktop and mobile", async ({
  page,
}) => {
  await signIn(page);
  await page
    .getByRole("combobox", { name: "Owner for Describe meaningful images" })
    .selectOption({ label: "Alex Morgan" });
  await expect(
    page.getByRole("combobox", {
      name: "Owner for Describe meaningful images",
    }),
  ).toHaveValue(/\d+/);
  await page
    .getByRole("combobox", { name: "Status for Describe meaningful images" })
    .selectOption("in_progress");
  await expect(
    page.getByRole("combobox", {
      name: "Status for Describe meaningful images",
    }),
  ).toHaveValue("in_progress");
  await page.screenshot({
    path: path.join(captures, "overview.png"),
    fullPage: true,
    animations: "disabled",
  });
  const desktop = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    desktop.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await page.getByRole("button", { name: "Billing", exact: true }).click();
  await expect(page.getByText("in_fixture_0", { exact: true })).toBeVisible();
  await expect(page.getByText("in_fixture_1", { exact: true })).toBeVisible();
  await page.screenshot({
    path: path.join(captures, "billing.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "The work, in order." }),
  ).toBeVisible();
  await expect(page.locator(".timeline article").first()).toBeVisible();
  await page.screenshot({
    path: path.join(captures, "activity.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: path.join(captures, "mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const mobile = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    mobile.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
});

test("create site, process a real queued audit and isolate workspace data", async ({
  page,
}) => {
  await signIn(page);
  await page.getByRole("button", { name: "Add website", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Website name").fill(`Workflow check ${Date.now()}`);
  await dialog.getByLabel("HTTPS URL").fill("https://example.com/");
  await dialog
    .getByRole("button", { name: "Add website", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your next audit starts here." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Run audit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Describe meaningful images" }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".snapshot-note .status")).toHaveText("succeeded");
  await page
    .getByRole("combobox", { name: "Sample page", exact: true })
    .selectOption("healthy");
  await page.getByRole("button", { name: "Run audit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Clear on these checks." }),
  ).toBeVisible({ timeout: 20_000 });
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Personal sandbox" });
  await expect(
    page.getByRole("heading", { name: "A clean slate." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Billing", exact: true }).click();
  await expect(
    page.getByText("No invoices are available for this workspace."),
  ).toBeVisible();
  await expect(
    page.getByText("in_fixture_0", { exact: true }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});

test("session boundary keeps the login screen until fresh workspace data arrives", async ({
  page,
}) => {
  await signIn(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  let release!: () => void;
  let captured!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requested = new Promise<void>((resolve) => {
    captured = resolve;
  });
  await page.route("**/api/workspaces", async (route) => {
    captured();
    await gate;
    await route.continue();
  });
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.DEMO_PASSWORD || "");
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await requested;
  try {
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    await expect(
      page.getByRole("heading", { name: "Welcome back." }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Make the next move count." }),
    ).not.toBeVisible();
  } finally {
    release();
  }
  await expect(
    page.getByRole("heading", { name: "Make the next move count." }),
  ).toBeVisible();
});

test("mobile sign-out remains visible and clears the session", async ({
  page,
}) => {
  await signIn(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});
