function resolveApiBaseUrl() {
  if (typeof window !== 'undefined' && window.__FLORA_API_BASE__) {
    return String(window.__FLORA_API_BASE__).replace(/\/$/, '');
  }
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const h = window.location.hostname;
    if (h && h !== '') {
      return `http://${h}:8000`;
    }
  }
  return 'http://localhost:8000';
}

export const API_BASE_URL = resolveApiBaseUrl();
const API_V1 = `${API_BASE_URL}/api/v1`;

function isJwtAuth401Detail(detail) {
  if (typeof detail !== 'string' || !detail.trim()) {
    return true;
  }
  return /could not validate credentials|not authenticated|неверн.*токен|invalid token/i.test(detail);
}

async function readErrorDetail(response) {
  try {
    const body = await response.json();
    if (Array.isArray(body.detail)) {
      return body.detail.map((e) => e.msg || JSON.stringify(e)).join('; ');
    }
    if (typeof body.detail === 'object' && body.detail !== null) {
      return JSON.stringify(body.detail);
    }
    return body.detail || `Request failed: ${response.status}`;
  } catch {
    return `Request failed: ${response.status}`;
  }
}

const ACCESS_TOKEN_KEY = 'florist_access_token';

function getToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

function buildHeaders(extra = {}) {
  const token = getToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra
  };
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    if (response.status === 401) {
      const detail = await readErrorDetail(response);
      if (isJwtAuth401Detail(detail)) {
        throw new Error(
          'Нужен вход в аккаунт: откройте «Профиль», войдите или зарегистрируйтесь. ' +
            'Если вы уже входили — выйдите и войдите снова (сессия могла устареть).'
        );
      }
      throw new Error(detail);
    }
    const detail = await readErrorDetail(response);
    throw new Error(detail);
  }
  return response.json();
}

export async function fetchFlowers({ offset = 0, limit = 20 } = {}) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return requestJson(`${API_V1}/flowers?${params.toString()}`);
}

export async function fetchBouquets({ offset = 0, limit = 8, published_only = true } = {}) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
    published_only: String(Boolean(published_only))
  });
  return requestJson(`${API_V1}/bouquets?${params.toString()}`);
}

export async function createBouquet(payload) {
  return requestJson(`${API_V1}/bouquets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    body: JSON.stringify(payload)
  });
}

export async function updateBouquet(bouquetId, payload) {
  return requestJson(`${API_V1}/bouquets/${bouquetId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    body: JSON.stringify(payload)
  });
}

export async function deleteBouquet(bouquetId) {
  const response = await fetch(`${API_V1}/bouquets/${bouquetId}`, {
    method: 'DELETE',
    headers: buildHeaders()
  });
  if (!response.ok) {
    let detail = 'Request failed';
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = `${detail}: ${response.status}`;
    }
    throw new Error(detail);
  }
}

export async function uploadBouquetImage(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_V1}/bouquets/upload-image`, {
    method: 'POST',
    headers: buildHeaders(),
    body: formData
  });
  if (!response.ok) {
    let detail = 'Request failed';
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = `${detail}: ${response.status}`;
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function fetchAiFlowers() {
  return requestJson(`${API_V1}/ai/flowers`);
}

export async function generateAiBouquet(payload) {
  return requestJson(`${API_V1}/ai/generate-bouquet`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildHeaders()
    },
    body: JSON.stringify(payload)
  });
}

/** Сохраняет сгенерированное изображение как букет пользователя (для корзины). Нужен JWT. */
export async function saveAiBouquetSnapshotForCart(body) {
  return requestJson(`${API_V1}/ai/snapshot-for-cart`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    body: JSON.stringify(body)
  });
}

export async function registerUser({ email, full_name, password }) {
  return requestJson(`${API_V1}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, full_name, password })
  });
}

export async function verifyEmail({ email, code }) {
  return requestJson(`${API_V1}/auth/verify-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code })
  });
}

export async function loginUser({ email, password }) {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_V1}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body
  });

  if (!response.ok) {
    throw new Error('Неверный email или пароль');
  }

  const data = await response.json();
  setToken(data.access_token);
  return data;
}

export async function fetchCurrentUser() {
  return requestJson(`${API_V1}/users/me`, {
    headers: buildHeaders()
  });
}

export async function fetchOrders({ offset = 0, limit = 20 } = {}) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return requestJson(`${API_V1}/orders?${params.toString()}`, {
    headers: buildHeaders()
  });
}

export async function fetchAdminOrders({ offset = 0, limit = 50 } = {}) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return requestJson(`${API_V1}/orders/admin?${params}`, {
    headers: buildHeaders()
  });
}

export async function patchAdminOrderComplete(orderId, completed) {
  return requestJson(`${API_V1}/orders/${Number(orderId)}/admin-complete`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    body: JSON.stringify({ completed: Boolean(completed) })
  });
}

export async function createOrder({ bouquet_id, quantity = 1, delivery_address, user_comment = null }) {
  const body = {
    bouquet_id: Number(bouquet_id),
    quantity: Number(quantity) || 1,
    delivery_address: String(delivery_address).trim()
  };
  if (user_comment != null && String(user_comment).trim()) {
    body.user_comment = String(user_comment).trim().slice(0, 2000);
  }
  return requestJson(`${API_V1}/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    body: JSON.stringify(body)
  });
}

export async function passwordResetRequest({ email }) {
  return requestJson(`${API_V1}/auth/password-reset/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
}

export async function passwordResetConfirm({ email, code, new_password }) {
  return requestJson(`${API_V1}/auth/password-reset/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code, new_password })
  });
}

export function getAuthToken() {
  return getToken();
}

/** Проверка адреса доставки в Новосибирске (геокодер на бэкенде). */
export async function validateDeliveryAddress(address) {
  return requestJson(`${API_V1}/geo/validate-address`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address: String(address).trim() })
  });
}

/** Подсказки адреса по частичной строке (Новосибирск). */
export async function suggestDeliveryAddresses(q) {
  const query = encodeURIComponent(String(q).trim());
  return requestJson(`${API_V1}/geo/suggest-address?q=${query}`);
}
