const { test, expect } = require('@playwright/test');

test.describe('Weather demo web app', () => {
  test('searching a valid city displays current weather', async ({ page }) => {
    await page.goto('/');
    await page.fill('#city', 'London');
    await page.click('button[type="submit"]');
    await expect(page.locator('#current')).toBeVisible();
    await expect(page.locator('#city-name')).toContainText('london');
    await expect(page.locator('#condition')).not.toBeEmpty();
    await expect(page.locator('#temperature')).not.toBeEmpty();
  });

  test('forecast section lists five days', async ({ page }) => {
    await page.goto('/');
    await page.fill('#city', 'Berlin');
    await page.click('button[type="submit"]');
    await expect(page.locator('#forecast')).toBeVisible();
    await expect(page.locator('.forecast-day')).toHaveCount(5);
  });

  test('temperatures are displayed in Celsius', async ({ page }) => {
    // DEFECT: the UI renders Fahrenheit but labels the value as Celsius.
    await page.goto('/');
    await page.fill('#city', 'Rome');
    await page.click('button[type="submit"]');
    await expect(page.locator('#temperature')).toContainText('°F', { useInnerText: false });
    // The requirement is °C; a °F reading is a UAT failure.
    const text = await page.locator('#temperature').innerText();
    expect(text.trim().endsWith('°F'), `expected Celsius, got: ${text}`).toBe(false);
  });

  test('invalid city search shows an error and clears stale results', async ({ page }) => {
    // DEFECT: stale weather remains on screen after an invalid search.
    await page.goto('/');
    await page.fill('#city', 'London');
    await page.click('button[type="submit"]');
    await expect(page.locator('#current')).toBeVisible();

    await page.fill('#city', 'Atlantis');
    await page.click('button[type="submit"]');
    await expect(page.locator('#error')).toBeVisible();
    // Requirement: previous results must be cleared.
    await expect(page.locator('#current')).toBeHidden();
  });

  test('application remains usable after an invalid search', async ({ page }) => {
    await page.goto('/');
    await page.fill('#city', 'Atlantis');
    await page.click('button[type="submit"]');
    await expect(page.locator('#error')).toBeVisible();

    await page.fill('#city', 'Paris');
    await page.click('button[type="submit"]');
    await expect(page.locator('#current')).toBeVisible();
    await expect(page.locator('#city-name')).toContainText('paris');
  });
});
