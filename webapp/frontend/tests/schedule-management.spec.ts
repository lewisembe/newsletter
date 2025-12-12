import { test, expect } from '@playwright/test';

test.describe('Schedule Management - Error 422 Bug Fix', () => {
  test('should load scheduled executions without 422 error', async ({ page }) => {
    // Navigate directly to login page
    await page.goto('https://lewisembe.duckdns.org/login');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Login
    await page.getByPlaceholder(/correo|email/i).fill('admin@example.com');
    await page.getByPlaceholder(/contraseña|password/i).fill('admin123');
    await page.getByRole('button', { name: /entrar|sign in|iniciar/i }).click();

    // Wait for successful login (dashboard should appear)
    await page.waitForURL(/dashboard/);
    await expect(page).toHaveURL(/dashboard/);

    // Navigate to Admin section
    await page.getByRole('link', { name: 'Administración' }).click();

    // Wait for Admin page to load
    await page.waitForLoadState('networkidle');

    // Listen for network requests to the schedules endpoint
    let schedulesRequestStatus = 0;
    let schedulesRequestError = '';
    page.on('response', response => {
      if (response.url().includes('/api/v1/stage-executions/schedules')) {
        schedulesRequestStatus = response.status();
        console.log(`Schedules endpoint response: ${response.status()}`);
        if (response.status() !== 200) {
          response.text().then(body => {
            schedulesRequestError = body;
            console.log(`Error body: ${body}`);
          });
        }
      }
    });

    // Click on "Stage Executions" tab
    await page.getByText('⚙️ Stage Executions').click();

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Click on "Ejecuciones Programadas" button/link
    await page.getByText('Ejecuciones Programadas').click();

    // Wait for the schedules to load
    await page.waitForTimeout(2000);

    // Verify that the request to schedules endpoint was successful (not 422)
    expect(schedulesRequestStatus).toBe(200);

    // Verify that the page shows the schedule management UI
    await expect(page.getByText(/crear programación|create schedule/i)).toBeVisible();

    // Verify no error message is displayed
    const errorMessage = page.getByText(/request failed|error/i);
    if (await errorMessage.isVisible()) {
      throw new Error('Error message still visible on page');
    }

    console.log('✅ Schedule management page loaded successfully without 422 error');
  });
});
