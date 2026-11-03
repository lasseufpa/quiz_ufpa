// Menu lateral (hambúrguer) do painel do apresentador.
// O botão "?" é um link direto para o guia (abre em outra aba, definido no HTML).

(function () {
    const menu = document.getElementById('side-menu');
    const overlay = document.getElementById('side-menu-overlay');
    const menuToggle = document.getElementById('menu-toggle');
    const closeBtn = document.getElementById('side-menu-close');

    if (!menu || !menuToggle || !overlay) return;

    function openMenu() {
        menu.classList.add('open');
        overlay.classList.add('open');
        menu.setAttribute('aria-hidden', 'false');
    }

    function closeMenu() {
        menu.classList.remove('open');
        overlay.classList.remove('open');
        menu.setAttribute('aria-hidden', 'true');
    }

    menuToggle.addEventListener('click', () => {
        if (menu.classList.contains('open')) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    closeBtn.addEventListener('click', closeMenu);
    overlay.addEventListener('click', closeMenu);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && menu.classList.contains('open')) closeMenu();
    });
})();
