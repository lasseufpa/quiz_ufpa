const { test, expect } = require('@playwright/test');

test('host runs a quiz and player answers', async ({ context }) => {
  const playerPage = await context.newPage();
  await playerPage.goto('/');

  await playerPage.getByPlaceholder('Seu nome').fill('Alice');
  await playerPage.getByRole('button', { name: 'Entrar' }).click();
  await expect(playerPage.getByText('Sala de espera')).toBeVisible();

  const hostPage = await context.newPage();
  await hostPage.goto('/host/login');
  await hostPage.getByPlaceholder('Senha do host').fill('admin123');
  await hostPage.getByRole('button', { name: 'Entrar' }).click();
  await hostPage.waitForURL('**/host');

  const startButton = hostPage.getByRole('button', { name: /Iniciar jogo/ });
  await expect(startButton).toBeEnabled();

  await hostPage.getByRole('combobox').selectOption('e2e_quiz');
  await startButton.click();

  await expect(playerPage.getByText('Pergunta em andamento')).toBeVisible();
  await playerPage.locator('.option-btn').first().click();

  await expect(playerPage.getByText('Resultado', { exact: true })).toBeVisible();
});
