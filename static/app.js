// ==========================================================================
// FLASH 3.2 — INTERAÇÕES, GERENCIAMENTO DE TEMA & SERVICE WORKER
// ==========================================================================

// 1. Gerenciamento do Modo Escuro / Claro
(function() {
  function updateThemeUI(theme) {
    const isDark = theme === 'dark';
    document.documentElement.setAttribute('data-theme', theme);

    // Atualiza botões de alternância de tema
    const buttons = document.querySelectorAll('.theme-toggle-btn');
    buttons.forEach(btn => {
      btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
      btn.setAttribute('title', isDark ? 'Mudar para modo claro' : 'Mudar para modo escuro');
      const label = btn.querySelector('.theme-toggle-label');
      if (label) {
        label.textContent = isDark ? 'Modo Claro' : 'Modo Escuro';
      }
    });

    // Atualiza a meta tag de cor do navegador (theme-color) para status bars mobile
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.setAttribute('content', isDark ? '#090d16' : '#f59e0b');
    }
  }

  function initTheme() {
    let currentTheme = document.documentElement.getAttribute('data-theme');
    if (!currentTheme) {
      try {
        const saved = localStorage.getItem('flash-theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        currentTheme = (saved === 'dark' || (!saved && prefersDark)) ? 'dark' : 'light';
      } catch (e) {
        currentTheme = 'light';
      }
    }
    updateThemeUI(currentTheme);

    // Intercepta cliques nos botões de alternância de tema
    document.addEventListener('click', function(e) {
      const btn = e.target.closest('.theme-toggle-btn');
      if (!btn) return;
      e.preventDefault();
      const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      const nextTheme = current === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem('flash-theme', nextTheme);
      } catch (err) {}
      updateThemeUI(nextTheme);
    });

    // Escuta preferências do sistema operacional se o usuário não tiver escolha salva
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        try {
          if (!localStorage.getItem('flash-theme')) {
            updateThemeUI(e.matches ? 'dark' : 'light');
          }
        } catch (err) {}
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }
})();

// 2. Registro do Service Worker (Progressive Web App)
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
