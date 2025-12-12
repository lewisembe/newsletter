import { test, expect } from '@playwright/test';

/**
 * Debug test to diagnose login issues
 */

test('debug login flow', async ({ page }) => {
  // Enable verbose logging
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err));

  // Navigate to login page
  await page.goto('/login');
  await page.screenshot({ path: 'test-results/01-login-page.png' });

  // Check that we're on the login page
  await expect(page).toHaveURL(/\/login/);
  console.log('✓ Navigated to login page');

  // Wait for form to be visible
  await page.waitForSelector('input[type="email"]', { state: 'visible' });
  await page.waitForSelector('input[type="password"]', { state: 'visible' });
  console.log('✓ Login form is visible');

  // Fill the form
  await page.fill('input[type="email"]', 'admin@example.com');
  await page.fill('input[type="password"]', 'admin123');
  await page.screenshot({ path: 'test-results/02-form-filled.png' });
  console.log('✓ Form filled with credentials');

  // Listen for network requests
  page.on('response', response => {
    if (response.url().includes('login')) {
      console.log(`LOGIN RESPONSE: ${response.status()} ${response.statusText()}`);
      response.json().then(data => console.log('RESPONSE DATA:', data)).catch(() => {});
    }
  });

  // Submit the form
  await page.click('button[type="submit"]');
  console.log('✓ Submit button clicked');

  // Wait a bit to see what happens
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'test-results/03-after-submit.png' });

  // Check current URL
  const currentUrl = page.url();
  console.log('Current URL after login:', currentUrl);

  // Check for error messages
  const errorMessage = await page.locator('text=/error/i').count();
  if (errorMessage > 0) {
    const errorText = await page.locator('text=/error/i').first().textContent();
    console.log('ERROR MESSAGE:', errorText);
  }

  // Check if we got redirected to dashboard
  if (currentUrl.includes('/dashboard')) {
    console.log('✓ Successfully redirected to dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  } else {
    console.log('✗ Still on login page - login failed');
    await page.screenshot({ path: 'test-results/04-login-failed.png' });
  }
});
