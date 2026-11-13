import { initAiChat } from './ai-chat.js';
import {
  API_BASE_URL,
  createBouquet,
  createOrder,
  deleteBouquet,
  fetchAdminOrders,
  fetchAiFlowers,
  patchAdminOrderComplete,
  fetchBouquets,
  fetchCurrentUser,
  fetchOrders,
  fetchFlowers,
  passwordResetConfirm,
  passwordResetRequest,
  uploadBouquetImage,
  updateBouquet,
  getAuthToken,
  loginUser,
  registerUser,
  suggestDeliveryAddresses,
  validateDeliveryAddress
} from './api.js';
import { topBouquets } from './data.js';
import { renderHeader, setActiveNav } from './header.js';

const pageNodes = Array.from(document.querySelectorAll('.page'));
const headerNode = document.getElementById('site-header');
const bouquetGrid = document.getElementById('bouquet-grid');
const catalogGrid = document.getElementById('catalog-grid');
const catalogSearchInput = document.querySelector('#page-catalog .search-input');
const catalogPriceLabels = Array.from(document.querySelectorAll('#page-catalog .filter-block:nth-of-type(1) label'));
const catalogTypeFilterBlock = document.querySelector('#page-catalog .filter-block:nth-of-type(2)');
const aiCtaButton = document.getElementById('ai-cta-btn');
const aiFlowersHint = document.getElementById('ai-flowers-hint');
const authStatus = document.getElementById('auth-status');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');

// Cart / favorites / profile containers
const cartStatus = document.getElementById('cart-status');
const cartItemsNode = document.getElementById('cart-items');
const cartItemsCountNode = document.getElementById('cart-items-count');
const cartItemsTotalNode = document.getElementById('cart-items-total');
const cartTotalNode = document.getElementById('cart-total');
const cartSuggestionsNode = document.getElementById('cart-suggestions');

const favoritesCountNode = document.getElementById('favorites-count');
const favoritesItemsNode = document.getElementById('favorites-items');
const favoritesAddAllBtn = document.getElementById('favorites-add-all');
const favoritesClearBtn = document.getElementById('favorites-clear');

const profileStatus = document.getElementById('profile-status');
const profileAuthPanel = document.getElementById('profile-auth-panel');
const profileAuthStatus = document.getElementById('profile-auth-status');
const profileLoginForm = document.getElementById('profile-login-form');
const profileRegisterForm = document.getElementById('profile-register-form');
const profileLayoutNode = document.querySelector('#page-profile .profile-layout');
const profileEditBtn = document.getElementById('profile-edit-btn');
const profileCancelBtn = document.getElementById('profile-cancel-btn');
const profileSaveBtn = document.getElementById('profile-save-btn');
const logoutBtn = document.getElementById('logout-btn');
const ordersListNode = document.getElementById('orders-list');
const profileContentTabs = document.getElementById('profile-content-tabs');
const profilePanelMain = document.getElementById('profile-panel-main');
const profilePanelOrders = document.getElementById('profile-panel-orders');
const profileTabBtnMain = document.getElementById('profile-tab-btn-main');
const profileTabBtnOrders = document.getElementById('profile-tab-btn-orders');
const ordersAllLink = document.getElementById('orders-all-link');
const profileFavoritesCountNode = document.getElementById('profile-favorites-count');
const favoritesPreviewNode = document.getElementById('favorites-preview');
const adminPanel = document.getElementById('admin-panel');
const adminStatus = document.getElementById('admin-status');
const adminBouquetForm = document.getElementById('admin-bouquet-form');
const adminBouquetId = document.getElementById('admin-bouquet-id');
const adminNameInput = document.getElementById('admin-name');
const adminDescriptionInput = document.getElementById('admin-description');
const adminPriceInput = document.getElementById('admin-price');
const adminOldPriceInput = document.getElementById('admin-old-price');
const adminBadgeInput = document.getElementById('admin-badge');
const adminImageFileInput = document.getElementById('admin-image-file');
const adminPublishedInput = document.getElementById('admin-published');
const adminFormResetBtn = document.getElementById('admin-form-reset');
const adminBouquetsList = document.getElementById('admin-bouquets-list');
const adminOrdersList = document.getElementById('admin-orders-list');

const profileFirstNameInput = document.getElementById('profile-first-name');
const profileLastNameInput = document.getElementById('profile-last-name');
const profileEmailInput = document.getElementById('profile-email');
const profilePhoneInput = document.getElementById('profile-phone');
const profileAddressInput = document.getElementById('profile-address');
const profileBirthdateInput = document.getElementById('profile-birthdate');
const profileGenderSelect = document.getElementById('profile-gender');
const profileForgotBtn = document.getElementById('profile-forgot-btn');

const profileLoginEmailInput = document.getElementById('profile-login-email');
const profileLoginPasswordInput = document.getElementById('profile-login-password');

const profileRegisterEmailInput = document.getElementById('profile-register-email');

const profileForgotPanel = document.getElementById('profile-forgot-panel');
const profileForgotStatus = document.getElementById('profile-forgot-status');
const profileResetCodeInput = document.getElementById('profile-reset-code');
const profileResetNewPasswordInput = document.getElementById('profile-reset-new-password');
const profileResetConfirmBtn = document.getElementById('profile-reset-confirm-btn');
const profileResetCancelBtn = document.getElementById('profile-reset-cancel-btn');

const profileVerifyPanel = document.getElementById('profile-verify-panel');
const profileVerifyHint = document.getElementById('profile-verify-hint');
const profileVerifyCodeInput = document.getElementById('profile-verify-code');
const profileVerifyConfirmBtn = document.getElementById('profile-verify-confirm-btn');
const profileVerifyBackBtn = document.getElementById('profile-verify-back-btn');

let activePage = 'home';

const uiItemsIndex = new Map();

const CART_STORAGE_KEY = 'florist_cart_v1';
const FAVORITES_STORAGE_KEY = 'florist_favorites_v1';
const DELIVERY_ADDRESS_STORAGE_KEY = 'florist_delivery_address_v1';

const profileAuthState = {
  pendingEmail: null,
  pendingPassword: null,
  pendingResetEmail: null,
};

const loadedOnce = {
  profile: false
};

const catalogState = {
  allCards: []
};

const currentSession = {
  user: null,
  adminBouquets: [],
  adminOrders: [],
  editingImageUrl: null,
  editingFlowers: {}
};

function getActivePage() {
  return activePage;
}

function showProfileRegisterForm() {
  // Show profile auth UI as registration form (no token).
  if (profileAuthPanel) profileAuthPanel.style.display = 'block';
  if (profileLayoutNode) profileLayoutNode.style.display = 'none';

  const tabLoginBtn = document.getElementById('profile-auth-tab-login');
  const tabRegisterBtn = document.getElementById('profile-auth-tab-register');
  const panelLogin = document.getElementById('profile-auth-login');
  const panelRegister = document.getElementById('profile-auth-register');

  const isLogin = false;
  if (tabLoginBtn) tabLoginBtn.classList.toggle('is-active', isLogin);
  if (tabLoginBtn) tabLoginBtn.setAttribute('aria-selected', isLogin ? 'true' : 'false');
  if (tabRegisterBtn) tabRegisterBtn.classList.toggle('is-active', !isLogin);
  if (tabRegisterBtn) tabRegisterBtn.setAttribute('aria-selected', !isLogin ? 'true' : 'false');

  if (panelLogin) panelLogin.style.display = isLogin ? 'block' : 'none';
  if (panelRegister) panelRegister.style.display = !isLogin ? 'block' : 'none';
}

function extractBouquetMeta(item) {
  const meta = item && item.flowers && typeof item.flowers === 'object' ? item.flowers._meta || {} : {};
  return {
    badge: typeof meta.badge === 'string' && meta.badge.trim() ? meta.badge.trim() : null,
    oldPrice: Number(meta.old_price) > 0 ? Number(meta.old_price) : null
  };
}

function mapBouquetToCard(item) {
  const meta = extractBouquetMeta(item);
  const rawImageUrl = item.image_url || '';
  const normalizedImageUrl = rawImageUrl
    ? (rawImageUrl.startsWith('/') ? `${API_BASE_URL}${rawImageUrl}` : rawImageUrl)
    : '';
  const flowerTypes = Object.keys(item?.flowers || {})
    .filter((key) => key !== '_meta')
    .map((key) => String(key).toLowerCase().trim());
  return {
    id: item.id,
    name: item.name,
    description: item.description || 'Авторский букет от флориста',
    price: Number(item.price) || 0,
    oldPrice: meta.oldPrice,
    badge: meta.badge,
    flowerTypes,
    imageUrl:
      normalizedImageUrl ||
      'https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=900&q=80'
  };
}

function resetAdminForm() {
  if (!adminBouquetForm) return;
  if (adminBouquetId) adminBouquetId.value = '';
  if (adminNameInput) adminNameInput.value = '';
  if (adminDescriptionInput) adminDescriptionInput.value = '';
  if (adminPriceInput) adminPriceInput.value = '';
  if (adminOldPriceInput) adminOldPriceInput.value = '';
  if (adminBadgeInput) adminBadgeInput.value = '';
  if (adminImageFileInput) adminImageFileInput.value = '';
  if (adminPublishedInput) adminPublishedInput.checked = true;
  currentSession.editingImageUrl = null;
  currentSession.editingFlowers = {};
}

function fillAdminForm(item) {
  if (!item) return;
  const meta = extractBouquetMeta(item);
  if (adminBouquetId) adminBouquetId.value = String(item.id);
  if (adminNameInput) adminNameInput.value = item.name || '';
  if (adminDescriptionInput) adminDescriptionInput.value = item.description || '';
  if (adminPriceInput) adminPriceInput.value = String(Number(item.price) || 0);
  if (adminOldPriceInput) adminOldPriceInput.value = meta.oldPrice ? String(meta.oldPrice) : '';
  if (adminBadgeInput) adminBadgeInput.value = meta.badge || '';
  if (adminImageFileInput) adminImageFileInput.value = '';
  if (adminPublishedInput) adminPublishedInput.checked = Boolean(item.is_published);
  const flowers = item.flowers && typeof item.flowers === 'object' ? { ...item.flowers } : {};
  currentSession.editingFlowers = flowers;
  currentSession.editingImageUrl = item.image_url || null;
}

function renderAdminBouquetList() {
  if (!adminBouquetsList) return;
  const list = currentSession.adminBouquets || [];
  if (!list.length) {
    adminBouquetsList.innerHTML = '<p class="section-text">Карточек пока нет.</p>';
    return;
  }
  adminBouquetsList.innerHTML = list
    .map((b) => {
      const meta = extractBouquetMeta(b);
      return `
        <div class="admin-list__row">
          <div>
            <div><b>${b.name}</b></div>
            <div class="section-text">ID: ${b.id} · ${Number(b.price).toLocaleString('ru-RU')} ₽ · ${b.is_published ? 'Опубликован' : 'Скрыт'}</div>
            ${meta.badge ? `<div class="section-text">Акция: ${meta.badge}${meta.oldPrice ? ` (старая цена ${Number(meta.oldPrice).toLocaleString('ru-RU')} ₽)` : ''}</div>` : ''}
          </div>
          <div class="admin-list__actions">
            <button class="btn btn--secondary admin-edit-bouquet" data-id="${b.id}" type="button">Редактировать</button>
            <button class="btn profile-sidebar__logout admin-delete-bouquet" data-id="${b.id}" type="button">Удалить</button>
          </div>
        </div>
      `;
    })
    .join('');
}

function renderAdminOrdersList() {
  if (!adminOrdersList) return;
  const list = currentSession.adminOrders || [];
  if (!list.length) {
    adminOrdersList.innerHTML = '<p class="section-text">Заказов пока нет.</p>';
    return;
  }
  adminOrdersList.innerHTML = list
    .map((o) => {
      const thumb = absolutizeMediaUrl(o.bouquet_image_url) || CART_THUMB_PLACEHOLDER;
      const num = escapeHtml(o.order_number || `№${String(o.id).padStart(6, '0')}`);
      const bname = escapeHtml(o.bouquet_name || '');
      const cust = escapeHtml(o.customer_email || '');
      const cname = escapeHtml(o.customer_full_name || '');
      const addr = escapeHtml(o.delivery_address || '');
      const comment = o.user_comment ? escapeHtml(o.user_comment) : '—';
      const st = escapeHtml(String(o.status || ''));
      const when = o.created_at ? escapeHtml(new Date(o.created_at).toLocaleString('ru-RU')) : '—';
      const done = Boolean(o.admin_marked_complete_at);
      return `
        <article class="admin-order-card">
          <img class="admin-order-card__img" src="${thumb}" alt="" loading="lazy" />
          <div class="admin-order-card__body">
            <div class="admin-order-card__headline">
              <div class="admin-order-card__title">${num} · ${formatPriceRub(o.total_price)}</div>
              <label class="admin-order-card__done-wrap">
                <input type="checkbox" class="admin-order-card__done" data-order-id="${o.id}" ${done ? 'checked' : ''} />
                <span>Выполнен</span>
              </label>
            </div>
            <div class="section-text">${bname} × ${o.quantity}</div>
            <div class="section-text">Клиент: ${cname} (${cust})</div>
            <div class="section-text">Адрес: ${addr}</div>
            <div class="admin-order-card__comment"><span class="admin-order-card__comment-label">Комментарий:</span> ${comment}</div>
            <div class="section-text">Статус: ${st} · ${when}</div>
          </div>
        </article>
      `;
    })
    .join('');
}

async function loadAdminPanel() {
  if (!adminPanel) return;
  try {
    const all = await fetchBouquets({ offset: 0, limit: 100, published_only: false });
    currentSession.adminBouquets = Array.isArray(all) ? all : [];
    renderAdminBouquetList();
    if (adminStatus) adminStatus.textContent = 'Управляйте карточками товаров, акциями и публикацией.';
  } catch (error) {
    if (adminStatus) adminStatus.textContent = `Не удалось загрузить карточки: ${error.message}`;
  }
  try {
    const adminOrders = await fetchAdminOrders({ offset: 0, limit: 80 });
    currentSession.adminOrders = Array.isArray(adminOrders) ? adminOrders : [];
    renderAdminOrdersList();
  } catch {
    currentSession.adminOrders = [];
    if (adminOrdersList) adminOrdersList.innerHTML = '<p class="section-text">Заказы недоступны (нужны права админа).</p>';
  }
}

function navigateTo(pageKey) {
  const token = getAuthToken();
  const mustBeAuthorized = pageKey === 'favorites' || pageKey === 'basket';
  const redirectToProfile = mustBeAuthorized && !token;

  const finalPageKey = redirectToProfile ? 'profile' : pageKey;
  activePage = finalPageKey;

  pageNodes.forEach((node) => {
    const isActive = node.dataset.page === finalPageKey;
    node.classList.toggle('page--active', isActive);
  });

  setActiveNav(headerNode, finalPageKey);
  window.location.hash = finalPageKey;

  if (redirectToProfile) {
    showProfileRegisterForm();
  }

  if (finalPageKey === 'basket') {
    renderCartPage();
  }
  if (finalPageKey === 'favorites') {
    renderFavoritesPage();
  }
  if (finalPageKey === 'profile' && !loadedOnce.profile) {
    loadedOnce.profile = true;
    loadProfilePage();
  }
}

function mapFlowerToCard(flower) {
  return {
    id: flower.id,
    name: flower.name,
    description: flower.description || `${flower.category}, ${flower.color}`,
    price: Number(flower.price_per_unit) || 0,
    imageUrl:
      flower.image_url ||
      'https://images.unsplash.com/photo-1525310072745-f49212b5ac6d?auto=format&fit=crop&w=900&q=80'
  };
}

function cardTemplate(item) {
  return `
    <article class="card">
      <div class="card__media">
        ${item.badge ? `<span class="card__badge">${item.badge}</span>` : ''}
        <img class="card__image" src="${item.imageUrl}" alt="${item.name}" loading="lazy" />
      </div>
      <div class="card__body">
        <h3 class="card__title">${item.name}</h3>
        <p class="card__description">${item.description}</p>
        <div class="card__price-row">
          <p class="card__price">${item.price.toLocaleString('ru-RU')} ₽</p>
          ${item.oldPrice ? `<p class="card__old-price">${item.oldPrice.toLocaleString('ru-RU')} ₽</p>` : ''}
        </div>
        <div class="card__actions">
          <button
            class="btn btn--primary card-action"
            data-action="cart"
            data-id="${item.id}"
            type="button"
          >
            В корзину
          </button>
          <button
            class="btn btn--secondary card-action"
            data-action="favorites"
            data-id="${item.id}"
            type="button"
          >
            В избранное
          </button>
        </div>
      </div>
    </article>
  `;
}

function renderCards(targetNode, cards) {
  if (!Array.isArray(cards)) return;
  cards.forEach((item) => {
    if (item && typeof item.id !== 'undefined') {
      uiItemsIndex.set(item.id, item);
    }
  });
  targetNode.innerHTML = cards.map(cardTemplate).join('');
}

function normalizeCatalogText(value) {
  return String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function getActiveCatalogPriceRanges() {
  return catalogPriceLabels
    .map((label) => {
      const checkbox = label.querySelector('input[type="checkbox"]');
      if (!checkbox || !checkbox.checked) return null;
      const text = normalizeCatalogText(label.textContent);
      if (text.includes('до 2000')) return [0, 2000];
      if (text.includes('2000') && text.includes('5000')) return [2000, 5000];
      if (text.includes('5000') && text.includes('10000')) return [5000, 10000];
      return null;
    })
    .filter(Boolean);
}

function getActiveCatalogFlowerTypes() {
  if (!catalogTypeFilterBlock) return [];
  return Array.from(catalogTypeFilterBlock.querySelectorAll('label'))
    .map((label) => {
      const checkbox = label.querySelector('input[type="checkbox"]');
      if (!checkbox || !checkbox.checked) return null;
      return normalizeCatalogText(label.textContent);
    })
    .filter(Boolean);
}

function prettifyFlowerType(value) {
  const t = String(value || '').trim();
  if (!t) return '';
  return t[0].toUpperCase() + t.slice(1);
}

function renderCatalogFlowerTypeFilters(cards) {
  if (!catalogTypeFilterBlock) return;
  const checked = new Set(getActiveCatalogFlowerTypes());
  const allTypes = Array.from(
    new Set(
      (Array.isArray(cards) ? cards : [])
        .flatMap((card) => (Array.isArray(card.flowerTypes) ? card.flowerTypes : []))
        .map((t) => normalizeCatalogText(t))
        .filter(Boolean)
    )
  ).sort((a, b) => a.localeCompare(b, 'ru'));

  if (allTypes.length === 0) {
    catalogTypeFilterBlock.innerHTML = '<h4>Тип цветов</h4><p class="section-text">Нет данных</p>';
    return;
  }

  const labelsHtml = allTypes
    .map(
      (type) =>
        `<label><input type="checkbox" value="${type}" ${checked.has(type) ? 'checked' : ''}/> ${prettifyFlowerType(type)}</label>`
    )
    .join('');
  catalogTypeFilterBlock.innerHTML = `<h4>Тип цветов</h4>${labelsHtml}`;
}

function cardMatchesFlowerType(card, type) {
  const t = normalizeCatalogText(type);
  if (!t) return true;
  const haystack = normalizeCatalogText(`${card.name} ${card.description}`);
  const types = Array.isArray(card.flowerTypes) ? card.flowerTypes : [];
  return haystack.includes(t) || types.some((ft) => normalizeCatalogText(ft).includes(t));
}

function applyCatalogFilters() {
  if (!catalogGrid) return;
  const searchQuery = normalizeCatalogText(catalogSearchInput?.value || '');
  const activeRanges = getActiveCatalogPriceRanges();
  const activeTypes = getActiveCatalogFlowerTypes();

  const filtered = catalogState.allCards.filter((card) => {
    const textHaystack = normalizeCatalogText(`${card.name} ${card.description}`);
    const searchOk = !searchQuery || textHaystack.includes(searchQuery);
    const priceOk =
      activeRanges.length === 0 ||
      activeRanges.some(([min, max]) => Number(card.price) >= min && Number(card.price) <= max);
    const typeOk = activeTypes.length === 0 || activeTypes.some((type) => cardMatchesFlowerType(card, type));
    return searchOk && priceOk && typeOk;
  });

  if (!filtered.length) {
    catalogGrid.innerHTML = '<p class="section-text">По вашему фильтру букеты не найдены.</p>';
    return;
  }
  renderCards(catalogGrid, filtered);
}

function setCatalogCards(cards) {
  catalogState.allCards = Array.isArray(cards) ? cards : [];
  renderCatalogFlowerTypeFilters(catalogState.allCards);
  applyCatalogFilters();
}

function formatPriceRub(value) {
  const n = Number(value) || 0;
  return `${n.toLocaleString('ru-RU')} ₽`;
}

const CART_THUMB_PLACEHOLDER =
  'https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=240&q=70';

function absolutizeMediaUrl(url) {
  const s = String(url || '').trim();
  if (!s) return '';
  const api = String(API_BASE_URL || '').replace(/\/$/, '');
  if (s.startsWith('http://') || s.startsWith('https://')) {
    try {
      const parsed = new URL(s);
      if (parsed.pathname.startsWith('/api/v1/')) {
        return `${api}${parsed.pathname}${parsed.search}${parsed.hash}`;
      }
    } catch {
      // fall through
    }
    return s;
  }
  if (s.startsWith('/')) return `${api}${s}`;
  return s;
}

function normalizeCartLineItem(rawItem) {
  if (!rawItem || typeof rawItem !== 'object') return rawItem;
  const rawImg = rawItem.imageUrl || rawItem.image_url || rawItem.bouquet_image_url;
  return {
    id: Number(rawItem.id),
    name: rawItem.name != null ? String(rawItem.name) : '',
    description: rawItem.description != null ? String(rawItem.description) : '',
    price: Number(rawItem.price ?? rawItem.price_per_unit) || 0,
    imageUrl: absolutizeMediaUrl(rawImg)
  };
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function readCart() {
  try {
    const arr = JSON.parse(localStorage.getItem(CART_STORAGE_KEY) || '[]');
    if (!Array.isArray(arr)) return [];
    return arr
      .map((entry) => {
        if (!entry || !entry.item) return null;
        const item = normalizeCartLineItem(entry.item);
        if (!Number.isFinite(Number(item.id))) return null;
        return {
          ...entry,
          quantity: Number(entry.quantity) || 0,
          item
        };
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

function writeCart(cart) {
  localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
}

function readFavorites() {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function writeFavorites(favorites) {
  localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favorites));
}

function addToCart(item, quantity = 1) {
  const normalized = normalizeCartLineItem(item);
  const cart = readCart();
  const id = Number(normalized.id);
  const existing = cart.find((entry) => Number(entry.item.id) === id);
  if (existing) {
    existing.quantity += quantity;
    existing.item = normalizeCartLineItem({ ...existing.item, ...normalized });
  } else {
    cart.push({ item: normalized, quantity });
  }
  writeCart(cart);
}

function addToFavorites(item) {
  const favorites = readFavorites();
  const id = Number(item.id);
  const exists = favorites.some((f) => Number(f.id) === id);
  if (!exists) favorites.push(item);
  writeFavorites(favorites);
}

function updateCartQuantity(id, delta) {
  const cart = readCart();
  const entry = cart.find((e) => Number(e.item.id) === Number(id));
  if (!entry) return;
  entry.quantity += delta;
  if (entry.quantity <= 0) {
    writeCart(cart.filter((e) => Number(e.item.id) !== Number(id)));
  } else {
    writeCart(cart);
  }
  if (activePage === 'basket') renderCartPage();
}

function removeFromFavorites(id) {
  const favorites = readFavorites();
  writeFavorites(favorites.filter((f) => Number(f.id) !== Number(id)));
  if (activePage === 'favorites') renderFavoritesPage();
  if (activePage === 'profile') renderProfileFavoritesPreview();
}

function handleCardAction(id, action) {
  const item = uiItemsIndex.get(Number(id));
  if (!item) return;

  if (action === 'cart') {
    if (!getAuthToken()) {
      // Block cart actions until user is registered/logged in.
      navigateTo('profile');
      showProfileRegisterForm();
      return;
    }
    addToCart(item, 1);
    if (activePage === 'basket') renderCartPage();
  }

  if (action === 'favorites') {
    addToFavorites(item);
    if (activePage === 'favorites') renderFavoritesPage();
    if (activePage === 'profile') renderProfileFavoritesPreview();
  }
}

function cartItemTemplate(entry) {
  const id = Number(entry.item.id);
  const qty = Number(entry.quantity) || 0;
  const unitPrice = Number(entry.item.price) || 0;
  const lineTotal = unitPrice * qty;
  const thumbRaw = entry.item.imageUrl || entry.item.image_url || entry.item.bouquet_image_url;
  const thumb = thumbRaw && String(thumbRaw).trim() ? absolutizeMediaUrl(thumbRaw) : CART_THUMB_PLACEHOLDER;
  const title = escapeHtml(entry.item.name);
  const desc = escapeHtml(entry.item.description || '');
  return `
    <div class="cart-item" data-id="${id}">
      <img class="cart-item__thumb" src="${thumb}" alt="${title}" loading="lazy" />
      <div>
        <div class="cart-item__title">${title}</div>
        <div class="cart-item__desc">${desc}</div>
        <div class="cart-item__desc"><b>${formatPriceRub(unitPrice)}</b> за шт.</div>
      </div>
      <div class="cart-item__controls">
        <div class="qty">
          <button class="cart-qty-btn" type="button" data-id="${id}" data-delta="-1" aria-label="Уменьшить">-</button>
          <span>${qty}</span>
          <button class="cart-qty-btn" type="button" data-id="${id}" data-delta="1" aria-label="Увеличить">+</button>
        </div>
        <div class="cart-item__desc"><b>${formatPriceRub(lineTotal)}</b></div>
      </div>
    </div>
  `;
}

function renderCartPage() {
  if (!cartItemsNode) return;
  const cart = readCart();

  const totalQty = cart.reduce((acc, e) => acc + (Number(e.quantity) || 0), 0);
  const itemsTotal = cart.reduce((acc, e) => {
    const price = Number(e.item.price) || 0;
    const qty = Number(e.quantity) || 0;
    return acc + price * qty;
  }, 0);

  cartStatus.textContent = `У вас ${totalQty} товаров в корзине`;
  cartItemsCountNode.textContent = String(totalQty);
  cartItemsTotalNode.textContent = formatPriceRub(itemsTotal);
  cartTotalNode.textContent = formatPriceRub(itemsTotal);

  cartItemsNode.innerHTML = cart.length ? cart.map(cartItemTemplate).join('') : '<p class="section-text">Корзина пока пуста.</p>';

  // Suggestions: show 3 items not in cart (or fallback to first 3).
  const cartIds = new Set(cart.map((e) => Number(e.item.id)));
  const suggestions = topBouquets.filter((b) => !cartIds.has(Number(b.id))).slice(0, 3);
  const fallback = suggestions.length ? suggestions : topBouquets.slice(0, 3);
  renderCards(cartSuggestionsNode, fallback);
}

async function handleCartCheckout() {
  const cart = readCart();
  if (!cart.length) {
    window.alert('Корзина пуста.');
    return;
  }
  if (!getAuthToken()) {
    navigateTo('profile');
    showProfileRegisterForm();
    return;
  }
  let address = '';
  try {
    const raw = localStorage.getItem(DELIVERY_ADDRESS_STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      address = typeof data === 'string' ? String(data).trim() : String(data?.line || data?.normalized || '').trim();
    }
  } catch {
    // ignore
  }
  if (!address) {
    window.alert('Укажите адрес доставки на вкладке «Доставка» и сохраните его (опция «Запомнить адрес»).');
    navigateTo('delivery');
    return;
  }
  const commentEl = document.getElementById('cart-order-comment');
  const userComment = commentEl ? String(commentEl.value || '').trim() : '';
  const createdNumbers = [];
  try {
    for (const entry of cart) {
      const id = Number(entry.item.id);
      const qty = Number(entry.quantity) || 1;
      if (!Number.isFinite(id)) continue;
      const res = await createOrder({
        bouquet_id: id,
        quantity: qty,
        delivery_address: address,
        user_comment: userComment || null
      });
      if (res && res.order_number) createdNumbers.push(res.order_number);
    }
    writeCart([]);
    if (commentEl) commentEl.value = '';
    renderCartPage();
    window.alert(
      createdNumbers.length ? `Оформлено: ${createdNumbers.join(', ')}. Смотреть — в профиле.` : 'Заказы оформлены.'
    );
    loadedOnce.profile = false;
    navigateTo('profile');
    if (getAuthToken()) await loadProfilePage();
  } catch (e) {
    window.alert(e instanceof Error ? e.message : 'Не удалось оформить заказ.');
  }
}

function favoriteCardTemplate(item) {
  return `
    <article class="card">
      <div class="card__media">
        <img class="card__image" src="${item.imageUrl}" alt="${item.name}" loading="lazy" />
      </div>
      <div class="card__body">
        <h3 class="card__title">${item.name}</h3>
        <p class="card__description">${item.description || ''}</p>
        <div class="card__price-row">
          <p class="card__price">${formatPriceRub(item.price)}</p>
        </div>
        <div class="card__actions">
          <button class="btn btn--primary card-action" data-action="cart" data-id="${item.id}" type="button">В корзину</button>
          <button class="btn btn--secondary favorite-remove-action" data-id="${item.id}" type="button">Удалить</button>
        </div>
      </div>
    </article>
  `;
}

function renderFavoritesPage() {
  if (!favoritesItemsNode) return;
  const favorites = readFavorites();
  favoritesCountNode.textContent = `${favorites.length} букетов`;

  favorites.forEach((item) => {
    if (item && typeof item.id !== 'undefined') uiItemsIndex.set(Number(item.id), item);
  });

  favoritesItemsNode.innerHTML = favorites.length
    ? favorites.map(favoriteCardTemplate).join('')
    : '<p class="section-text">В избранном пока ничего нет.</p>';

  renderProfileFavoritesPreview();
}

function renderProfileFavoritesPreview() {
  if (!favoritesPreviewNode) return;
  const favorites = readFavorites();
  if (profileFavoritesCountNode) profileFavoritesCountNode.textContent = `${favorites.length} букетов`;

  const list = favorites.slice(0, 6);
  if (!list.length) {
    favoritesPreviewNode.innerHTML = '<p class="section-text">Сохраните несколько букетов — и они появятся здесь.</p>';
    return;
  }

  list.forEach((item) => {
    if (item && typeof item.id !== 'undefined') uiItemsIndex.set(Number(item.id), item);
  });

  favoritesPreviewNode.innerHTML = list
    .map(
      (item) => `
        <article class="card card--preview">
          <div class="card__media">
            <img class="card__image" src="${item.imageUrl}" alt="${item.name}" loading="lazy" />
          </div>
          <div class="card__body">
            <h3 class="card__title">${item.name}</h3>
            <p class="card__description">${item.description || ''}</p>
            <div class="card__actions card__actions--single">
              <button class="btn btn--primary card-action" data-action="cart" data-id="${item.id}" type="button">В корзину</button>
            </div>
          </div>
        </article>
      `
    )
    .join('');
}

function setProfileContentTab(tab) {
  const isMain = tab === 'main';
  if (profileTabBtnMain) {
    profileTabBtnMain.classList.toggle('is-active', isMain);
    profileTabBtnMain.setAttribute('aria-selected', isMain ? 'true' : 'false');
  }
  if (profileTabBtnOrders) {
    profileTabBtnOrders.classList.toggle('is-active', !isMain);
    profileTabBtnOrders.setAttribute('aria-selected', isMain ? 'false' : 'true');
  }
  if (profilePanelMain) profilePanelMain.classList.toggle('is-active', isMain);
  if (profilePanelOrders) profilePanelOrders.classList.toggle('is-active', !isMain);
}

function renderProfileOrdersList(orders) {
  if (!ordersListNode) return;
  const progressLabel = (o) => {
    if (o.progress_status) return escapeHtml(String(o.progress_status));
    return o.admin_marked_complete_at ? 'Готово' : 'В работе';
  };
  const progressClass = (o) =>
    o.admin_marked_complete_at || o.progress_status === 'Готово'
      ? 'order-row__progress--done'
      : 'order-row__progress--work';
  ordersListNode.innerHTML = orders.length
    ? orders
        .map((o) => {
          const thumb = absolutizeMediaUrl(o.bouquet_image_url) || CART_THUMB_PLACEHOLDER;
          const num = escapeHtml(o.order_number || `№${String(o.id).padStart(6, '0')}`);
          const bname = escapeHtml(o.bouquet_name || `Букет #${o.bouquet_id}`);
          const comment = o.user_comment
            ? `<div class="section-text order-row__comment">Комментарий: ${escapeHtml(o.user_comment)}</div>`
            : '';
          const when = o.created_at ? escapeHtml(new Date(o.created_at).toLocaleDateString('ru-RU')) : '—';
          const pl = progressLabel(o);
          const pc = progressClass(o);
          return `
              <div class="order-row">
                <img class="order-row__thumb" src="${thumb}" alt="" loading="lazy" />
                <div>
                  <div class="order-row__headline">
                    <div class="order-row__title">${num}</div>
                    <span class="order-row__progress ${pc}">${pl}</span>
                  </div>
                  <div class="section-text">${bname} · ${o.quantity} шт.</div>
                  <div class="section-text">Дата: ${when}</div>
                  ${comment}
                </div>
                <div class="section-text"><b>${formatPriceRub(o.total_price)}</b></div>
              </div>
            `;
        })
        .join('')
    : '<p class="section-text">История заказов пуста.</p>';
}

async function loadProfilePage() {
  if (profileStatus) profileStatus.textContent = 'Загружаю профиль...';
  const token = getAuthToken();
  if (!token) {
    if (profileAuthStatus) profileAuthStatus.textContent = 'Нужно войти, чтобы открыть профиль.';
    if (profileAuthPanel) profileAuthPanel.style.display = 'block';
    if (profileLayoutNode) profileLayoutNode.style.display = 'none';
    if (profileContentTabs) profileContentTabs.style.display = 'none';
    if (profileStatus) profileStatus.textContent = 'Вход обязателен для просмотра профиля.';
    return;
  }

  if (profileAuthPanel) profileAuthPanel.style.display = 'none';
  if (profileLayoutNode) profileLayoutNode.style.display = 'block';
  if (profileContentTabs) profileContentTabs.style.display = 'grid';

  try {
    const user = await fetchCurrentUser();
    currentSession.user = user;
    if (adminPanel) adminPanel.style.display = user.is_admin ? 'block' : 'none';
    if (profileFirstNameInput) {
      const parts = String(user.full_name || '').split(' ');
      profileFirstNameInput.value = parts[0] || '';
      profileLastNameInput.value = parts.slice(1).join(' ') || '';
      profileEmailInput.value = user.email || '';
    }
    // The PDF shows more fields; пока показываем заглушки.
    if (profilePhoneInput) profilePhoneInput.value = '+7 (999) 123-45-67';
    if (profileAddressInput) profileAddressInput.value = 'Москва, ул. Тверская, д. 12, кв. 45';
    if (profileBirthdateInput) profileBirthdateInput.value = '1990-05-15';

    renderProfileFavoritesPreview();
    if (user.is_admin) {
      await loadAdminPanel();
    }

    // Orders (authorized endpoint)
    try {
      const orders = await fetchOrders({ offset: 0, limit: 50 });
      renderProfileOrdersList(orders);
    } catch {
      if (ordersListNode) ordersListNode.innerHTML = '<p class="section-text">Не удалось загрузить заказы.</p>';
    }

    if (profileStatus) profileStatus.textContent = 'Профиль загружен.';
    setProfileEditMode(false);
  } catch {
    currentSession.user = null;
    if (adminPanel) adminPanel.style.display = 'none';
    if (profileContentTabs) profileContentTabs.style.display = 'none';
    if (profileStatus) profileStatus.textContent = 'Токен недействителен. Войдите заново.';
  }
}

function setProfileEditMode(isEditing) {
  if (!profileEditBtn || !profileCancelBtn || !profileSaveBtn) return;

  const inputs = [
    profileFirstNameInput,
    profileLastNameInput,
    profileEmailInput,
    profilePhoneInput,
    profileAddressInput,
    profileBirthdateInput,
    profileGenderSelect
  ].filter(Boolean);

  inputs.forEach((el) => {
    if (el.tagName === 'SELECT') {
      el.disabled = !isEditing;
    } else {
      el.disabled = !isEditing;
    }
  });

  const actions = document.getElementById('profile-actions');
  if (actions) actions.style.display = isEditing ? 'flex' : 'none';
}

async function loadTopCards() {
  try {
    const bouquets = await fetchBouquets({ offset: 0, limit: 100, published_only: true });
    if (Array.isArray(bouquets) && bouquets.length > 0) {
      const mapped = bouquets.map(mapBouquetToCard);
      renderCards(bouquetGrid, mapped);
      setCatalogCards(mapped);
      return;
    }
  } catch {
    // continue to fallback
  }

  try {
    const flowers = await fetchFlowers({ limit: 12 });
    if (Array.isArray(flowers) && flowers.length > 0) {
      const mapped = flowers.map(mapFlowerToCard);
      renderCards(bouquetGrid, mapped.slice(0, 8));
      setCatalogCards(mapped);
      return;
    }
  } catch {
    // continue to local mock
  }

  renderCards(bouquetGrid, topBouquets);
  setCatalogCards(topBouquets);
}

function initCatalogFiltering() {
  if (catalogSearchInput) {
    catalogSearchInput.addEventListener('input', applyCatalogFilters);
  }
  catalogPriceLabels.forEach((label) => {
    const checkbox = label.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.addEventListener('change', applyCatalogFilters);
    }
  });
  if (catalogTypeFilterBlock) {
    catalogTypeFilterBlock.addEventListener('change', (event) => {
      const target = event.target;
      if (target && target.matches('input[type="checkbox"]')) {
        applyCatalogFilters();
      }
    });
  }
}

function initRouting() {
  const hashPage = window.location.hash.replace('#', '').trim();
  const allowedPages = new Set(['home', 'catalog', 'delivery', 'ai', 'basket', 'favorites', 'profile']);
  navigateTo(allowedPages.has(hashPage) ? hashPage : 'home');

  window.addEventListener('hashchange', () => {
    const next = window.location.hash.replace('#', '').trim();
    if (allowedPages.has(next)) {
      navigateTo(next);
    }
  });
}

function initDeliveryAddressBlock() {
  const combo = document.getElementById('delivery-address-combo');
  const input = document.getElementById('delivery-address-input');
  const btn = document.getElementById('delivery-address-validate-btn');
  const feedback = document.getElementById('delivery-address-feedback');
  const remember = document.getElementById('delivery-remember-address');
  const list = document.getElementById('delivery-address-suggest');
  if (!combo || !input || !btn || !feedback || !remember || !list) return;

  const setFeedback = (text, kind) => {
    feedback.textContent = text;
    feedback.classList.remove('delivery-address-block__feedback--ok', 'delivery-address-block__feedback--err');
    if (kind === 'ok') feedback.classList.add('delivery-address-block__feedback--ok');
    if (kind === 'err') feedback.classList.add('delivery-address-block__feedback--err');
  };

  const readSavedDeliveryLine = () => {
    try {
      const raw = localStorage.getItem(DELIVERY_ADDRESS_STORAGE_KEY);
      if (!raw) return '';
      const data = JSON.parse(raw);
      if (typeof data === 'string') return String(data).trim();
      const normalized = String(data?.normalized || '').trim();
      const line = String(data?.line || '').trim();
      return normalized || line;
    } catch {
      return '';
    }
  };

  try {
    const raw = localStorage.getItem(DELIVERY_ADDRESS_STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      const line =
        typeof data === 'string'
          ? data
          : String(data?.line || data?.normalized || '').trim();
      if (line) {
        input.value = line;
        remember.checked = true;
      }
    }
  } catch {
    // ignore bad storage
  }

  const setListOpen = (open) => {
    input.setAttribute('aria-expanded', open ? 'true' : 'false');
    list.hidden = !open;
  };

  const hideSuggest = () => {
    list.innerHTML = '';
    setListOpen(false);
  };

  const mergeSavedFirst = (saved, apiList) => {
    const s = (saved || '').trim();
    if (!s) return (apiList || []).slice(0, 10);
    const norm = (t) => String(t).trim().toLowerCase();
    const ns = norm(s);
    const rest = (apiList || []).filter((x) => norm(x) !== ns);
    return [s, ...rest].slice(0, 10);
  };

  const renderSuggest = (items, hasSaved) => {
    list.innerHTML = '';
    if (!items.length) {
      hideSuggest();
      return;
    }
    items.forEach((text, index) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'presentation');
      const b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'option');
      const isSavedRow = Boolean(hasSaved) && index === 0;
      if (isSavedRow) {
        li.classList.add('delivery-address-suggest__item--saved');
        const main = document.createElement('span');
        main.textContent = text;
        const badge = document.createElement('small');
        badge.className = 'delivery-address-suggest__badge';
        badge.textContent = 'Сохранённый адрес';
        b.appendChild(main);
        b.appendChild(badge);
      } else {
        b.textContent = text;
      }
      b.addEventListener('click', () => {
        input.value = text;
        hideSuggest();
        setFeedback('', null);
      });
      li.appendChild(b);
      list.appendChild(li);
    });
    setListOpen(true);
  };

  let debounceId = null;
  const runSuggest = async () => {
    const q = input.value.trim();
    const saved = readSavedDeliveryLine();
    let api = [];
    if (q.length >= 2) {
      try {
        const res = await suggestDeliveryAddresses(q);
        if (Array.isArray(res?.suggestions)) api = res.suggestions;
      } catch {
        api = [];
      }
    }
    const merged = mergeSavedFirst(saved, api);
    if (!merged.length) {
      hideSuggest();
      return;
    }
    renderSuggest(merged, Boolean(saved));
  };

  const scheduleSuggest = () => {
    clearTimeout(debounceId);
    debounceId = setTimeout(() => {
      debounceId = null;
      void runSuggest();
    }, 320);
  };

  input.addEventListener('focus', () => {
    void runSuggest();
  });

  input.addEventListener('input', () => {
    scheduleSuggest();
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideSuggest();
  });

  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t instanceof Node && !combo.contains(t) && t !== btn) hideSuggest();
  });

  remember.addEventListener('change', () => {
    if (!remember.checked) {
      localStorage.removeItem(DELIVERY_ADDRESS_STORAGE_KEY);
      void runSuggest();
      return;
    }
    const v = input.value.trim();
    if (v) {
      localStorage.setItem(DELIVERY_ADDRESS_STORAGE_KEY, JSON.stringify({ line: v }));
    }
    void runSuggest();
  });

  btn.addEventListener('click', async () => {
    setFeedback('', null);
    hideSuggest();
    const addr = input.value.trim();
    if (addr.length < 3) {
      setFeedback('Введите улицу и дом (не короче 3 символов).', 'err');
      return;
    }
    btn.disabled = true;
    try {
      const res = await validateDeliveryAddress(addr);
      if (res.ok) {
        setFeedback(res.message || 'Адрес подтверждён.', 'ok');
        const normalized = res.normalized_address ? String(res.normalized_address).trim() : '';
        if (normalized) input.value = normalized;
        if (remember.checked) {
          localStorage.setItem(
            DELIVERY_ADDRESS_STORAGE_KEY,
            JSON.stringify({ line: input.value.trim(), normalized: normalized || null })
          );
        }
        void runSuggest();
      } else {
        setFeedback(res.message || 'Адрес не подходит для доставки.', 'err');
      }
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Не удалось проверить адрес.', 'err');
    } finally {
      btn.disabled = false;
    }
  });
}

async function loadAiFlowers() {
  try {
    const flowers = await fetchAiFlowers();
    const names = flowers.slice(0, 12).map((item) => item.name);
    aiFlowersHint.textContent =
      names.length > 0
        ? `Доступные цветы: ${names.join(', ')}`
        : 'Список цветов пока пуст.';
    return names;
  } catch {
    aiFlowersHint.textContent = 'Не удалось загрузить цветы с backend. Используются локальные подсказки.';
    return ['роза', 'тюльпан', 'пион', 'лилия', 'хризантема'];
  }
}

async function refreshAuthStatus() {
  if (!getAuthToken()) {
    authStatus.textContent = 'Вы не авторизованы.';
    return;
  }

  try {
    const user = await fetchCurrentUser();
    authStatus.textContent = `Вход выполнен: ${user.full_name} (${user.email})`;
  } catch {
    authStatus.textContent = 'Токен недействителен. Выполните вход снова.';
  }
}

function initAuthForms() {
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const email = String(formData.get('email') || '').trim();
    const password = String(formData.get('password') || '').trim();

    try {
      await loginUser({ email, password });
      await refreshAuthStatus();
      loginForm.reset();
    } catch (error) {
      authStatus.textContent = `Ошибка входа: ${error.message}`;
    }
  });

  registerForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(registerForm);
    const full_name = String(formData.get('fullName') || '').trim();
    const email = String(formData.get('email') || '').trim();
    const password = String(formData.get('password') || '').trim();

    try {
      await registerUser({ full_name, email, password });
      authStatus.textContent = 'Регистрация успешна. Теперь выполните вход.';
      registerForm.reset();
    } catch (error) {
      authStatus.textContent = `Ошибка регистрации: ${error.message}`;
    }
  });

  if (profileLoginForm) {
    profileLoginForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(profileLoginForm);
      const email = String(formData.get('email') || '').trim();
      const password = String(formData.get('password') || '').trim();

      try {
        await loginUser({ email, password });
        if (profileAuthStatus) profileAuthStatus.textContent = '';
        loadedOnce.profile = true;
        await loadProfilePage();
      } catch (error) {
        if (profileAuthStatus) {
          if (String(error.message || '').includes('Email is not verified')) {
            profileAuthStatus.textContent = 'Сначала подтвердите email кодом из письма.';
          } else {
            profileAuthStatus.textContent = `Ошибка входа: ${error.message}`;
          }
        }
      }
    });
  }

  if (profileRegisterForm) {
    profileRegisterForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(profileRegisterForm);
      const full_name = String(formData.get('fullName') || '').trim();
      const email = String(formData.get('email') || '').trim();
      const password = String(formData.get('password') || '').trim();

      try {
        await registerUser({ full_name, email, password });

        // Registration no longer requires email-code confirmation.
        if (profileAuthStatus) profileAuthStatus.textContent = 'Регистрация успешна. Теперь выполните вход.';
        profileRegisterForm.reset();

        // Pre-fill login so user can immediately sign in.
        setProfileAuthTab('login');
        if (profileLoginEmailInput) profileLoginEmailInput.value = email;
        if (profileLoginPasswordInput) profileLoginPasswordInput.value = password;
        if (profileForgotPanel) profileForgotPanel.style.display = 'none';
      } catch (error) {
        if (profileAuthStatus) profileAuthStatus.textContent = `Ошибка регистрации: ${error.message}`;
      }
    });
  }

  // Tabs for profile login/register
  const tabLoginBtn = document.getElementById('profile-auth-tab-login');
  const tabRegisterBtn = document.getElementById('profile-auth-tab-register');
  const panelLogin = document.getElementById('profile-auth-login');
  const panelRegister = document.getElementById('profile-auth-register');

  function setProfileAuthTab(tab) {
    const isLogin = tab === 'login';
    if (tabLoginBtn) tabLoginBtn.classList.toggle('is-active', isLogin);
    if (tabLoginBtn) tabLoginBtn.setAttribute('aria-selected', isLogin ? 'true' : 'false');
    if (tabRegisterBtn) tabRegisterBtn.classList.toggle('is-active', !isLogin);
    if (tabRegisterBtn) tabRegisterBtn.setAttribute('aria-selected', !isLogin ? 'true' : 'false');

    if (panelLogin) panelLogin.style.display = isLogin ? 'block' : 'none';
    if (panelRegister) panelRegister.style.display = isLogin ? 'none' : 'block';

    // Switch UI steps.
    if (isLogin) {
      if (profileForgotPanel) profileForgotPanel.style.display = 'none';
      // Verify step is a part of "register" flow.
      if (profileVerifyPanel) profileVerifyPanel.style.display = 'none';
    }
  }

  if (tabLoginBtn && tabRegisterBtn) {
    tabLoginBtn.addEventListener('click', () => setProfileAuthTab('login'));
    tabRegisterBtn.addEventListener('click', () => setProfileAuthTab('register'));
  }

  // Forgot password flow
  if (profileForgotBtn && profileForgotPanel) {
    profileForgotBtn.addEventListener('click', async () => {
      const email = profileLoginEmailInput ? String(profileLoginEmailInput.value || '').trim() : '';
      if (!email) {
        if (profileForgotStatus) profileForgotStatus.textContent = 'Введите email.';
        if (profileAuthStatus) profileAuthStatus.textContent = 'Введите email для сброса пароля.';
        return;
      }

      if (profileVerifyPanel) profileVerifyPanel.style.display = 'none';
      if (profileForgotPanel) profileForgotPanel.style.display = 'block';
      if (profileForgotStatus) profileForgotStatus.textContent = 'Отправляю код...';

      if (profileResetCodeInput) profileResetCodeInput.value = '';
      if (profileResetNewPasswordInput) profileResetNewPasswordInput.value = '';

      try {
        profileAuthState.pendingResetEmail = email;
        const data = await passwordResetRequest({ email });
        if (data && data.debug_code) {
          if (profileResetCodeInput) profileResetCodeInput.value = String(data.debug_code);
          if (profileForgotStatus) profileForgotStatus.textContent = 'Код получен (демо). Осталось ввести новый пароль.';
        } else {
          if (profileForgotStatus) profileForgotStatus.textContent = 'Код отправлен на email. Введите код и новый пароль.';
        }
      } catch (error) {
        if (profileForgotStatus) profileForgotStatus.textContent = `Ошибка: ${error.message}`;
      }
    });
  }

  if (profileResetCancelBtn && profileForgotPanel) {
    profileResetCancelBtn.addEventListener('click', () => {
      if (profileForgotPanel) profileForgotPanel.style.display = 'none';
      if (profileResetCodeInput) profileResetCodeInput.value = '';
      if (profileResetNewPasswordInput) profileResetNewPasswordInput.value = '';
      if (profileAuthState.pendingResetEmail) profileAuthState.pendingResetEmail = null;
    });
  }

  if (profileResetConfirmBtn && profileForgotPanel) {
    profileResetConfirmBtn.addEventListener('click', async () => {
      const email = profileAuthState.pendingResetEmail || (profileLoginEmailInput ? String(profileLoginEmailInput.value || '').trim() : '');
      const code = profileResetCodeInput ? String(profileResetCodeInput.value || '').trim() : '';
      const newPassword = profileResetNewPasswordInput ? String(profileResetNewPasswordInput.value || '').trim() : '';

      if (!email || !code || !newPassword) {
        if (profileForgotStatus) profileForgotStatus.textContent = 'Заполните код и новый пароль.';
        return;
      }

      if (profileForgotStatus) profileForgotStatus.textContent = 'Подтверждаю код и меняю пароль...';

      try {
        await passwordResetConfirm({ email, code, new_password: newPassword });
        if (profileForgotPanel) profileForgotPanel.style.display = 'none';
        if (profileAuthStatus) profileAuthStatus.textContent = 'Пароль изменен. Вы можете войти.';

        setProfileAuthTab('login');
        if (profileLoginEmailInput) profileLoginEmailInput.value = email;
        if (profileLoginPasswordInput) profileLoginPasswordInput.value = newPassword;
      } catch (error) {
        if (profileForgotStatus) profileForgotStatus.textContent = `Ошибка: ${error.message}`;
      }
    });
  }

  // Inline switch buttons inside auth panel
  document.querySelectorAll('[data-switch-to]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const to = btn.getAttribute('data-switch-to');
      if (to === 'login') setProfileAuthTab('login');
      if (to === 'register') setProfileAuthTab('register');
    });
  });
}

function initUiInteractions() {
  document.addEventListener('click', (event) => {
    const cardActionBtn = event.target.closest('.card-action');
    if (cardActionBtn) {
      const id = Number(cardActionBtn.getAttribute('data-id'));
      const action = cardActionBtn.getAttribute('data-action');
      handleCardAction(id, action);
      return;
    }

    const qtyBtn = event.target.closest('.cart-qty-btn');
    if (qtyBtn) {
      const id = Number(qtyBtn.getAttribute('data-id'));
      const delta = Number(qtyBtn.getAttribute('data-delta'));
      if (Number.isFinite(id) && delta !== 0) {
        updateCartQuantity(id, delta);
      }
      return;
    }

    const favoriteRemoveBtn = event.target.closest('.favorite-remove-action');
    if (favoriteRemoveBtn) {
      const id = Number(favoriteRemoveBtn.getAttribute('data-id'));
      removeFromFavorites(id);
      return;
    }
  });

  if (favoritesAddAllBtn) {
    favoritesAddAllBtn.addEventListener('click', () => {
      const favorites = readFavorites();
      favorites.forEach((f) => addToCart(f));
      renderCartPage();
    });
  }

  if (favoritesClearBtn) {
    favoritesClearBtn.addEventListener('click', () => {
      writeFavorites([]);
      renderFavoritesPage();
      // profile-favorites-preview uses same localStorage
      if (profileFavoritesCountNode) {
        const count = readFavorites().length;
        profileFavoritesCountNode.textContent = `${count} букетов`;
      }
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      localStorage.removeItem('florist_access_token');
      loadedOnce.profile = false;
      currentSession.user = null;
      currentSession.adminBouquets = [];
      currentSession.adminOrders = [];
      navigateTo('home');
      if (authStatus) authStatus.textContent = 'Вы не авторизованы.';
    });
  }

  if (adminFormResetBtn) {
    adminFormResetBtn.addEventListener('click', () => resetAdminForm());
  }

  if (adminBouquetForm) {
    adminBouquetForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!currentSession.user || !currentSession.user.is_admin) return;

      const flowers = currentSession.editingFlowers && typeof currentSession.editingFlowers === 'object'
        ? { ...currentSession.editingFlowers }
        : {};

      const badge = String(adminBadgeInput ? adminBadgeInput.value : '').trim();
      const oldPriceNum = Number(adminOldPriceInput ? adminOldPriceInput.value : 0);
      if (badge || oldPriceNum > 0) {
        flowers._meta = {
          ...(flowers._meta && typeof flowers._meta === 'object' ? flowers._meta : {}),
          ...(badge ? { badge } : {}),
          ...(oldPriceNum > 0 ? { old_price: oldPriceNum } : {})
        };
      } else if (flowers._meta) {
        delete flowers._meta;
      }

      const payload = {
        name: String(adminNameInput ? adminNameInput.value : '').trim(),
        description: String(adminDescriptionInput ? adminDescriptionInput.value : '').trim() || null,
        price: Number(adminPriceInput ? adminPriceInput.value : 0),
        flowers,
        image_url: currentSession.editingImageUrl || null,
        is_published: Boolean(adminPublishedInput && adminPublishedInput.checked)
      };

      if (!payload.name || payload.price <= 0) {
        if (adminStatus) adminStatus.textContent = 'Заполните название и цену.';
        return;
      }

      try {
        const file = adminImageFileInput && adminImageFileInput.files ? adminImageFileInput.files[0] : null;
        if (file) {
          const uploaded = await uploadBouquetImage(file);
          if (uploaded && uploaded.image_url) {
            payload.image_url = uploaded.image_url;
          }
        }

        const editId = Number(adminBouquetId ? adminBouquetId.value : 0);
        if (Number.isFinite(editId) && editId > 0) {
          await updateBouquet(editId, payload);
          if (adminStatus) adminStatus.textContent = `Карточка #${editId} обновлена.`;
        } else {
          await createBouquet(payload);
          if (adminStatus) adminStatus.textContent = 'Карточка создана.';
        }
        resetAdminForm();
        await loadAdminPanel();
        await loadTopCards();
      } catch (error) {
        if (adminStatus) adminStatus.textContent = `Ошибка сохранения: ${error.message}`;
      }
    });
  }

  if (adminBouquetsList) {
    adminBouquetsList.addEventListener('click', async (event) => {
      const editBtn = event.target.closest('.admin-edit-bouquet');
      if (editBtn) {
        const id = Number(editBtn.getAttribute('data-id'));
        const item = (currentSession.adminBouquets || []).find((b) => Number(b.id) === id);
        if (item) {
          fillAdminForm(item);
          if (adminStatus) adminStatus.textContent = `Редактирование карточки #${id}.`;
        }
        return;
      }

      const delBtn = event.target.closest('.admin-delete-bouquet');
      if (delBtn) {
        const id = Number(delBtn.getAttribute('data-id'));
        const confirmed = window.confirm(`Удалить карточку #${id}?`);
        if (!confirmed) return;
        try {
          await deleteBouquet(id);
          if (adminStatus) adminStatus.textContent = `Карточка #${id} удалена.`;
          await loadAdminPanel();
          await loadTopCards();
        } catch (error) {
          if (adminStatus) adminStatus.textContent = `Ошибка удаления: ${error.message}`;
        }
      }
    });
  }

  if (adminOrdersList) {
    adminOrdersList.addEventListener('change', async (event) => {
      const target = event.target;
      if (!target || target.type !== 'checkbox' || !target.classList.contains('admin-order-card__done')) return;
      const id = Number(target.getAttribute('data-order-id'));
      if (!Number.isFinite(id)) return;
      const want = target.checked;
      target.disabled = true;
      try {
        await patchAdminOrderComplete(id, want);
        await loadAdminPanel();
      } catch (err) {
        target.checked = !want;
        window.alert(err instanceof Error ? err.message : 'Ошибка');
      } finally {
        target.disabled = false;
      }
    });
  }

  if (profileEditBtn) {
    profileEditBtn.addEventListener('click', () => setProfileEditMode(true));
  }

  if (profileCancelBtn) {
    profileCancelBtn.addEventListener('click', () => setProfileEditMode(false));
  }

  if (profileSaveBtn) {
    profileSaveBtn.addEventListener('click', async () => {
      setProfileEditMode(false);
      // Do not show noisy "saved" status message.
      if (profileStatus) profileStatus.textContent = '';
    });
  }

  const cartCheckoutBtn = document.getElementById('cart-checkout-btn');
  const cartContinueBtn = document.getElementById('cart-continue-btn');
  if (cartCheckoutBtn) {
    cartCheckoutBtn.addEventListener('click', () => {
      void handleCartCheckout();
    });
  }
  if (cartContinueBtn) {
    cartContinueBtn.addEventListener('click', () => {
      navigateTo('catalog');
    });
  }
}

function initProfileContentTabs() {
  if (profileTabBtnMain) {
    profileTabBtnMain.addEventListener('click', () => setProfileContentTab('main'));
  }
  if (profileTabBtnOrders) {
    profileTabBtnOrders.addEventListener('click', () => {
      setProfileContentTab('orders');
      if (!getAuthToken()) return;
      void (async () => {
        try {
          const orders = await fetchOrders({ offset: 0, limit: 50 });
          renderProfileOrdersList(orders);
        } catch {
          if (ordersListNode) ordersListNode.innerHTML = '<p class="section-text">Не удалось загрузить заказы.</p>';
        }
      })();
    });
  }
  if (ordersAllLink) {
    const loadAll = async () => {
      if (!getAuthToken()) return;
      const prev = ordersAllLink.textContent;
      ordersAllLink.textContent = 'Загрузка...';
      try {
        const orders = await fetchOrders({ offset: 0, limit: 200 });
        renderProfileOrdersList(orders);
      } catch {
        if (ordersListNode) ordersListNode.innerHTML = '<p class="section-text">Не удалось загрузить заказы.</p>';
      } finally {
        ordersAllLink.textContent = prev || 'Все заказы';
      }
    };
    ordersAllLink.addEventListener('click', () => void loadAll());
    ordersAllLink.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        void loadAll();
      }
    });
  }
}

async function initApp() {
  renderHeader(headerNode, navigateTo, getActivePage);
  initCatalogFiltering();
  await loadTopCards();
  initRouting();
  initDeliveryAddressBlock();
  initAuthForms();
  initProfileContentTabs();
  initUiInteractions();
  await refreshAuthStatus();

  // Hide footer when scrolling down (saves screen space).
  const footer = document.querySelector('.site-footer');
  if (footer) {
    let lastScrollY = window.scrollY;
    let rafId = null;
    const thresholdPx = 10;

    const apply = () => {
      rafId = null;
      const currentY = window.scrollY;
      const isScrollingDown = currentY > lastScrollY + thresholdPx;
      const isScrollingUp = currentY < lastScrollY - thresholdPx;

      // Always show at the very top.
      if (currentY < 50) {
        footer.classList.remove('site-footer--hidden');
      } else if (isScrollingDown) {
        footer.classList.add('site-footer--hidden');
      } else if (isScrollingUp) {
        footer.classList.remove('site-footer--hidden');
      }

      lastScrollY = currentY;
    };

    window.addEventListener(
      'scroll',
      () => {
        if (rafId) return;
        rafId = requestAnimationFrame(apply);
      },
      { passive: true },
    );
  }

  aiCtaButton.addEventListener('click', () => navigateTo('ai'));

  const availableFlowers = await loadAiFlowers();
  initAiChat({
    form: document.getElementById('ai-form'),
    input: document.getElementById('ai-input'),
    messagesContainer: document.getElementById('ai-messages'),
    availableFlowers,
    getAuthToken,
    onRequireLogin: () => {
      navigateTo('profile');
      showProfileRegisterForm();
    },
    afterAddAiBouquetToCart: (cartItem) => {
      addToCart(cartItem, 1);
      uiItemsIndex.set(Number(cartItem.id), cartItem);
      navigateTo('basket');
    }
  });
}

initApp();
