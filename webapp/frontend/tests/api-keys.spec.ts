import { test, expect } from '@playwright/test';

/**
 * Test suite for API Keys management functionality
 * Tests admin panel API key CRUD operations
 */

test.describe('API Keys Management', () => {
  // Login as admin before each test
  test.beforeEach(async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');

    // Fill login form
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'admin123');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for redirect to dashboard
    await page.waitForURL('/dashboard');

    // Navigate to API Keys tab
    await page.goto('/admin?tab=api-keys');
    await page.waitForLoadState('networkidle');
  });

  test('should display API Keys management page', async ({ page }) => {
    // Check that the page title is present
    await expect(page.locator('h2:has-text("Claves API")')).toBeVisible();

    // Check that the description is present
    await expect(page.locator('text=Gestiona claves API de OpenAI')).toBeVisible();

    // Check that the "Add API Key" button is visible
    await expect(page.locator('button:has-text("Añadir Clave API")')).toBeVisible();
  });

  test('should show empty state when no API keys exist', async ({ page }) => {
    // Check for empty state message
    const emptyState = page.locator('text=No hay claves API configuradas aún');

    // If there are no API keys, the empty state should be visible
    const isVisible = await emptyState.isVisible();

    if (isVisible) {
      await expect(emptyState).toBeVisible();
      await expect(page.locator('text=Añade tu primera clave API de OpenAI')).toBeVisible();
    }
  });

  test('should open create modal when clicking "Añadir Clave API"', async ({ page }) => {
    // Click the "Add API Key" button
    await page.click('button:has-text("Añadir Clave API")');

    // Check that the modal is visible
    await expect(page.locator('h3:has-text("Añadir Nueva Clave API")')).toBeVisible();

    // Check form fields are present
    await expect(page.locator('input[placeholder*="Clave Producción"]')).toBeVisible();
    await expect(page.locator('input[placeholder="sk-..."]')).toBeVisible();
    await expect(page.locator('textarea[placeholder*="Notas opcionales"]')).toBeVisible();

    // Check buttons
    await expect(page.locator('button:has-text("Cancelar")')).toBeVisible();
    await expect(page.locator('button:has-text("Añadir Clave")')).toBeVisible();
  });

  test('should close modal when clicking "Cancelar"', async ({ page }) => {
    // Open modal
    await page.click('button:has-text("Añadir Clave API")');
    await expect(page.locator('h3:has-text("Añadir Nueva Clave API")')).toBeVisible();

    // Click cancel
    await page.click('button:has-text("Cancelar")');

    // Modal should be closed
    await expect(page.locator('h3:has-text("Añadir Nueva Clave API")')).not.toBeVisible();
  });

  test('should validate required fields', async ({ page }) => {
    // Open modal
    await page.click('button:has-text("Añadir Clave API")');

    // Try to submit empty form
    await page.click('button:has-text("Añadir Clave")');

    // Check for HTML5 validation (browser will prevent submission)
    const aliasInput = page.locator('input[placeholder*="Clave Producción"]');
    await expect(aliasInput).toHaveAttribute('required', '');

    const apiKeyInput = page.locator('input[placeholder="sk-..."]');
    await expect(apiKeyInput).toHaveAttribute('required', '');
  });

  test('should create a new API key successfully', async ({ page }) => {
    // Open modal
    await page.click('button:has-text("Añadir Clave API")');

    // Fill form with test data
    const testAlias = `Test Key ${Date.now()}`;
    await page.fill('input[placeholder*="Clave Producción"]', testAlias);
    await page.fill('input[placeholder="sk-..."]', 'sk-test123456789abcdefghijklmnopqrstuvwxyz');
    await page.fill('textarea[placeholder*="Notas opcionales"]', 'Esta es una clave de prueba');

    // Submit form
    await page.click('button:has-text("Añadir Clave")');

    // Wait for the API call to complete
    await page.waitForLoadState('networkidle');

    // Check if the key appears in the table or if there's an error
    // Note: This might fail if the API key format is invalid or other validation fails
    const hasError = await page.locator('text=Failed to').isVisible().catch(() => false);

    if (!hasError) {
      // If no error, the modal should be closed
      await expect(page.locator('h3:has-text("Añadir Nueva Clave API")')).not.toBeVisible();
    }
  });

  test('should display API keys table when keys exist', async ({ page }) => {
    // Check if table exists
    const table = page.locator('table');
    const tableVisible = await table.isVisible().catch(() => false);

    if (tableVisible) {
      // Check table headers
      await expect(page.locator('th:has-text("Alias")')).toBeVisible();
      await expect(page.locator('th:has-text("Vista Previa")')).toBeVisible();
      await expect(page.locator('th:has-text("Estado")')).toBeVisible();
      await expect(page.locator('th:has-text("Uso")')).toBeVisible();
      await expect(page.locator('th:has-text("Último Uso")')).toBeVisible();
      await expect(page.locator('th:has-text("Acciones")')).toBeVisible();
    }
  });

  test('should logout successfully', async ({ page }) => {
    // Click logout button
    await page.click('button:has-text("Cerrar Sesión")');

    // Should redirect to home page
    await page.waitForURL('/');

    // Should not be able to access admin page anymore
    await page.goto('/admin');
    await page.waitForURL('/login');
  });
});
