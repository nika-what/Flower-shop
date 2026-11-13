import { API_BASE_URL, generateAiBouquet, saveAiBouquetSnapshotForCart } from './api.js';
const FALLBACK_FLOWERS = ['роза', 'пион', 'гипсофила', 'тюльпан', 'лилия'];
const FLOWER_ALIASES = {
  лили: ['лилия'],
  лил: ['лилия'],
  лилий: ['лилия'],
  гипсо: ['гипсофила'],
  гипс: ['гипсофила'],
  роза: ['роза'],
  роз: ['роза'],
  розы: ['роза'],
  пион: ['пион'],
  пионы: ['пион'],
  тюльп: ['тюльпан'],
  тюльпан: ['тюльпан'],
  хриз: ['хризантема'],
  гвозд: ['гвоздика'],
  эуст: ['эустома'],
  орхид: ['орхидея'],
  сукк: ['суккулент'],
};

function normalizeToken(value) {
  return String(value || '').toLowerCase().replace(/[^a-zа-я0-9]+/gi, '');
}

function stem(value) {
  return normalizeToken(value).slice(0, 5);
}

function extractWords(value) {
  return String(value || '')
    .toLowerCase()
    .split(/[^a-zа-я0-9]+/gi)
    .map((word) => word.trim())
    .filter(Boolean);
}

function createMessageNode(role, text) {
  const message = document.createElement('article');
  message.className = `ai-msg ${role === 'user' ? 'ai-msg--user' : 'ai-msg--assistant'}`;
  message.textContent = text;
  return message;
}

function formatRub(value) {
  if (value == null || Number.isNaN(Number(value))) return '';
  return `${Math.round(Number(value)).toLocaleString('ru-RU')} ₽`;
}

function mapBouquetApiToCartItem(b) {
  const raw = String(b.image_url ?? b.imageUrl ?? '').trim();
  let imageRef = raw;
  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    try {
      const u = new URL(raw);
      imageRef = u.pathname.startsWith('/api/v1/') ? `${u.pathname}${u.search}` : raw;
    } catch {
      imageRef = raw;
    }
  }
  const imageUrl =
    !imageRef
      ? ''
      : imageRef.startsWith('http://') || imageRef.startsWith('https://')
        ? imageRef
        : imageRef.startsWith('/')
          ? `${API_BASE_URL}${imageRef}`
          : imageRef;
  return {
    id: Number(b.id),
    name: String(b.name || 'Букет'),
    description: String(b.description ?? ''),
    price: Number(b.price ?? b.price_per_unit) || 0,
    imageUrl: imageRef.startsWith('/') ? imageRef : imageUrl
  };
}

function createBouquetPreviewNode(imageUrl, priceMeta = null, cartMeta = null) {
  const message = document.createElement('article');
  message.className = 'ai-msg ai-msg--assistant';

  const text = document.createElement('p');
  text.className = 'ai-msg__text';
  text.textContent = 'Вот пример букета по вашему запросу';
  message.appendChild(text);

  if (priceMeta && (priceMeta.priceNote || priceMeta.estimatedTotalRub != null)) {
    const priceBlock = document.createElement('div');
    priceBlock.className = 'ai-msg__price-block';
    if (priceMeta.estimatedTotalRub != null && priceMeta.estimatedTotalRub > 0) {
      const totalLine = document.createElement('p');
      totalLine.className = 'ai-msg__price-total';
      totalLine.textContent = `Ориентировочная стоимость по каталогу: ${formatRub(priceMeta.estimatedTotalRub)}`;
      priceBlock.appendChild(totalLine);
    }
    if (priceMeta.priceNote) {
      const note = document.createElement('p');
      note.className = 'ai-msg__price-note';
      note.textContent = priceMeta.priceNote;
      priceBlock.appendChild(note);
    }
    const br = Array.isArray(priceMeta.breakdown) ? priceMeta.breakdown : [];
    const lines = br.filter((row) => row && (row.matched_catalog_items > 0 || row.avg_price_per_unit_rub != null));
    if (lines.length > 0) {
      const list = document.createElement('ul');
      list.className = 'ai-msg__price-breakdown';
      for (const row of lines) {
        const li = document.createElement('li');
        const sub = row.line_subtotal_rub != null ? formatRub(row.line_subtotal_rub) : '—';
        const avg =
          row.avg_price_per_unit_rub != null ? `${Number(row.avg_price_per_unit_rub).toLocaleString('ru-RU')} ₽/шт.` : '—';
        li.textContent = `${row.requested_name} × ${row.qty}: в среднем ${avg} по ${row.matched_catalog_items} поз. каталога → ${sub}`;
        list.appendChild(li);
      }
      priceBlock.appendChild(list);
    }
    message.appendChild(priceBlock);
  }

  if (imageUrl) {
    const img = document.createElement('img');
    img.className = 'ai-msg__image';
    img.src = imageUrl;
    img.alt = 'Сгенерированный букет';
    img.loading = 'lazy';
    message.appendChild(img);
  }

  const canCart =
    cartMeta &&
    typeof cartMeta.getAuthToken === 'function' &&
    typeof cartMeta.onRequireLogin === 'function' &&
    typeof cartMeta.afterAddAiBouquetToCart === 'function' &&
    cartMeta.firstImageRelative;

  if (canCart) {
    const actions = document.createElement('div');
    actions.className = 'ai-msg__actions';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn--primary ai-msg__cart-btn';
    btn.textContent = 'В корзину';
    btn.addEventListener('click', async () => {
      if (!cartMeta.getAuthToken()) {
        cartMeta.onRequireLogin();
        return;
      }
      const est = cartMeta.aiReply && cartMeta.aiReply.estimated_total_rub;
      const priceVal = est != null && !Number.isNaN(Number(est)) ? Math.max(0, Math.round(Number(est))) : 0;
      const titleBase = (cartMeta.userText || 'AI букет').trim().slice(0, 100);
      const flowers = (cartMeta.requestPayload && cartMeta.requestPayload.flowers) || [];
      const composition = Array.isArray(flowers)
        ? flowers
            .map((x) => (x && x.name ? `${String(x.name).trim()} × ${Number(x.qty) || 1}` : ''))
            .filter(Boolean)
            .join(', ')
        : '';
      const description =
        composition.length > 0
          ? `Состав: ${composition}`.slice(0, 2000)
          : titleBase
            ? `Запрос: ${titleBase}`.slice(0, 2000)
            : null;
      const body = {
        ai_image_path: String(cartMeta.firstImageRelative),
        name: titleBase ? `AI: ${titleBase}` : 'AI букет',
        description,
        price: priceVal,
        flowers: {
          source: 'ai',
          style: cartMeta.requestPayload && cartMeta.requestPayload.style,
          occasion: cartMeta.requestPayload && cartMeta.requestPayload.occasion,
          items: (cartMeta.requestPayload && cartMeta.requestPayload.flowers) || []
        }
      };
      btn.disabled = true;
      const prev = btn.textContent;
      btn.textContent = 'Добавляем…';
      try {
        const created = await saveAiBouquetSnapshotForCart(body);
        const item = mapBouquetApiToCartItem(created);
        cartMeta.afterAddAiBouquetToCart(item);
        btn.textContent = 'В корзине ✓';
      } catch (err) {
        btn.disabled = false;
        btn.textContent = prev;
        window.alert(err instanceof Error ? err.message : 'Ошибка');
      }
    });
    actions.appendChild(btn);
    message.appendChild(actions);
  }

  return message;
}

function inferStyle(message) {
  const text = message.toLowerCase();
  if (text.includes('романт') || text.includes('нежн')) {
    return 'romantic';
  }
  if (text.includes('ярк') || text.includes('контраст')) {
    return 'contrast';
  }
  return 'classic';
}

function flowerDisplayName(flower) {
  if (typeof flower === 'string') return flower.trim();
  const n = flower && flower.name != null ? String(flower.name).trim() : '';
  const lat = flower && flower.latin_name != null ? String(flower.latin_name).trim() : '';
  return n || lat || 'Цветок';
}

function flowerSearchText(flower) {
  if (typeof flower === 'string') return flower;
  return [flower?.name, flower?.latin_name, flower?.category, flower?.color].filter(Boolean).join(' ');
}

function pickFlowers(message, availableFlowers) {
  const stemsInMessage = new Set(extractWords(message).map(stem).filter(Boolean));
  for (const s of Array.from(stemsInMessage)) {
    const aliases = FLOWER_ALIASES[s];
    if (aliases) {
      aliases.forEach((name) => stemsInMessage.add(stem(name)));
    }
  }

  const selected = availableFlowers.filter((flower) => {
    const flowerWords = extractWords(flowerSearchText(flower));
    const flowerStems = flowerWords.length > 0 ? flowerWords.map(stem) : [stem(flowerDisplayName(flower))];
    return flowerStems.some((flowerStem) => flowerStem && stemsInMessage.has(flowerStem));
  });
  if (selected.length > 0) {
    return selected.slice(0, 5);
  }
  const fallbackPool = Array.isArray(availableFlowers) && availableFlowers.length > 0
    ? availableFlowers
    : FALLBACK_FLOWERS;
  return fallbackPool.slice(0, 3);
}

function pickFlowersWithQty(message, availableFlowers) {
  const selected = pickFlowers(message, availableFlowers);
  const text = message.toLowerCase();

  const pairs = [];
  const re = /(\d+)\s*([a-zа-я-]+)/gi;
  let m;
  while ((m = re.exec(text)) !== null) {
    const tokenStem = stem(m[2]);
    const qty = Number(m[1]) || 1;
    pairs.push({ qty, token: tokenStem });
    const aliases = FLOWER_ALIASES[tokenStem];
    if (aliases) {
      aliases.forEach((name) => pairs.push({ qty, token: stem(name) }));
    }
  }

  return selected.map((flower) => {
    const label = flowerDisplayName(flower);
    const nameStems = extractWords(label).map(stem);
    const matched = pairs.find((p) =>
      p.token && nameStems.some((nameStem) => nameStem && (p.token.startsWith(nameStem) || nameStem.startsWith(p.token)))
    );
    return { name: label, qty: matched ? Math.max(1, matched.qty) : 1 };
  });
}

export async function sendMessageToAI(message, availableFlowers = []) {
  const payload = {
    flowers: pickFlowersWithQty(message, availableFlowers),
    style: inferStyle(message),
    occasion: message,
    palette: null,
    budget_rub: null,
    wrap_type: null
  };
  const aiReply = await generateAiBouquet(payload);
  return { aiReply, requestPayload: payload };
}

export function initAiChat({
  form,
  input,
  messagesContainer,
  availableFlowers,
  getAuthToken: getTokenFn,
  onRequireLogin,
  afterAddAiBouquetToCart
}) {
  messagesContainer.appendChild(
    createMessageNode('assistant', 'Здравствуйте! Опишите повод, цветовую гамму и примерный бюджет букета.')
  );

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const userText = input.value.trim();
    if (!userText) {
      return;
    }

    messagesContainer.appendChild(createMessageNode('user', userText));
    form.querySelector('button[type="submit"]').disabled = true;
    input.value = '';

    try {
      const { aiReply, requestPayload } = await sendMessageToAI(userText, availableFlowers);
      const firstImage = Array.isArray(aiReply.images) && aiReply.images.length ? aiReply.images[0] : null;
      const firstImageRelative = firstImage ? String(firstImage) : '';
      const imageUrl = firstImageRelative
        ? firstImageRelative.startsWith('/')
          ? `${API_BASE_URL}${firstImageRelative}`
          : firstImageRelative
        : '';
      messagesContainer.appendChild(
        createBouquetPreviewNode(
          imageUrl,
          {
            estimatedTotalRub: aiReply.estimated_total_rub,
            priceNote: aiReply.price_note,
            breakdown: aiReply.price_breakdown
          },
          getTokenFn && onRequireLogin && afterAddAiBouquetToCart
            ? {
                firstImageRelative,
                userText,
                aiReply,
                requestPayload,
                getAuthToken: getTokenFn,
                onRequireLogin,
                afterAddAiBouquetToCart
              }
            : null
        )
      );
    } catch (error) {
      messagesContainer.appendChild(
        createMessageNode('assistant', `Не удалось получить ответ от AI: ${error.message}`)
      );
    } finally {
      form.querySelector('button[type="submit"]').disabled = false;
      input.focus();
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
}
