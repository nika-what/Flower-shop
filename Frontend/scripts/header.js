const navigationItems = [
  { key: 'home', label: 'Главная' },
  { key: 'catalog', label: 'Каталог' },
  { key: 'delivery', label: 'Доставка' }
];

function setMenuOpen(container, nav, toggleButton, backdrop, open) {
  nav.classList.toggle('nav--open', open);
  container.classList.toggle('site-header--menu-open', open);
  if (toggleButton) {
    toggleButton.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggleButton.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
  }
  if (backdrop) {
    backdrop.hidden = !open;
    backdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
  }
}

export function renderHeader(container, onNavigate, getActivePage) {
  container.innerHTML = `
    <div class="nav-backdrop" id="nav-backdrop" hidden aria-hidden="true"></div>
    <div class="container header-inner">
      <a href="#home" class="logo" data-nav-link="home">FloraBloom</a>

      <button class="menu-toggle" id="menu-toggle" type="button" aria-expanded="false" aria-controls="main-nav" aria-label="Открыть меню">☰</button>

      <nav class="nav" id="main-nav" aria-label="Главная навигация">
        ${navigationItems
          .map(
            (item) =>
              `<button class="nav__link ${item.key === getActivePage() ? 'is-active' : ''}" data-nav-link="${item.key}" type="button">${item.label}</button>`
          )
          .join('')}
      </nav>

      <div class="header-actions" aria-label="Быстрые действия">
        <button class="icon-btn" type="button" title="Корзина" data-nav-link="basket">🛒</button>
        <button class="icon-btn" type="button" title="Избранное" data-nav-link="favorites">💐</button>
        <button class="icon-btn" type="button" title="Профиль" data-nav-link="profile">👤</button>
      </div>
    </div>
  `;

  const nav = container.querySelector('#main-nav');
  const toggleButton = container.querySelector('#menu-toggle');
  const backdrop = container.querySelector('#nav-backdrop');

  const closeMenu = () => setMenuOpen(container, nav, toggleButton, backdrop, false);

  toggleButton.addEventListener('click', () => {
    const next = !nav.classList.contains('nav--open');
    setMenuOpen(container, nav, toggleButton, backdrop, next);
  });

  if (backdrop) {
    backdrop.addEventListener('click', closeMenu);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('nav--open')) {
      closeMenu();
    }
  });

  container.querySelectorAll('[data-nav-link]').forEach((element) => {
    element.addEventListener('click', (event) => {
      event.preventDefault();
      const targetPage = element.getAttribute('data-nav-link');
      onNavigate(targetPage);
      closeMenu();
    });
  });
}

export function setActiveNav(container, activePage) {
  container.querySelectorAll('.nav__link').forEach((btn) => {
    const isActive = btn.getAttribute('data-nav-link') === activePage;
    btn.classList.toggle('is-active', isActive);
  });
}
