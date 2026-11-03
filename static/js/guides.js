// Guias de uso: cada aba mostra apenas o tutorial escolhido.
// A aba fica na URL (#editor, #administrador...) para poder ser compartilhada
// e para que os atalhos do menu do apresentador abram o guia certo.

(function () {
    const tabs = Array.from(document.querySelectorAll('.guide-tab'));
    const sections = Array.from(document.querySelectorAll('.guide-section'));
    if (!tabs.length || !sections.length) return;

    const ids = tabs.map(t => t.dataset.guide);

    function apply(id, options) {
        const opts = options || {};
        if (!ids.includes(id)) id = ids[0];

        tabs.forEach(tab => {
            const ativo = tab.dataset.guide === id;
            tab.classList.toggle('active', ativo);
            tab.setAttribute('aria-selected', ativo ? 'true' : 'false');
            tab.tabIndex = ativo ? 0 : -1;
        });

        sections.forEach(section => {
            section.hidden = section.id !== id;
        });

        if (opts.updateHash !== false) {
            history.replaceState(null, '', '#' + id);
        }
        if (opts.scroll) {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    function idFromHash() {
        return (window.location.hash || '').replace('#', '');
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => apply(tab.dataset.guide, { scroll: true }));

        // Setas do teclado trocam de aba, como em uma abas de verdade
        tab.addEventListener('keydown', (e) => {
            let destino = null;
            if (e.key === 'ArrowRight') destino = (index + 1) % tabs.length;
            else if (e.key === 'ArrowLeft') destino = (index - 1 + tabs.length) % tabs.length;
            else if (e.key === 'Home') destino = 0;
            else if (e.key === 'End') destino = tabs.length - 1;
            if (destino === null) return;
            e.preventDefault();
            tabs[destino].focus();
            apply(tabs[destino].dataset.guide, { scroll: true });
        });
    });

    window.addEventListener('hashchange', () => apply(idFromHash()));

    // Abre já no guia pedido pelo link (ex.: /guia#editor)
    apply(idFromHash());
})();
