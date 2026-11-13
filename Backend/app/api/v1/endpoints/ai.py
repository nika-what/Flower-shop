import base64
import hashlib
import re
import shutil
import statistics
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_user_optional
from app.core.config import settings
from app.core.database import get_db
from app.crud.bouquet import bouquet_crud
from app.crud.flower import flower_crud
from app.models.bouquet import Bouquet as BouquetRow
from app.models.flower import Flower as FlowerRow
from app.models.user import User
from app.schemas.bouquet import Bouquet as BouquetRead, BouquetCreate
from app.schemas.flower import Flower

router = APIRouter(prefix='/ai', tags=['ai'])
logger = logging.getLogger(__name__)

# Версия поведения API (для проверки, что uvicorn поднят с актуальным кодом).
AI_ROUTER_BUILD = 'gigachat-kandinsky-diagnostics-retry-20260330d'


def _prompt_looks_like_http_glitch(text: str) -> bool:
    """Текст ответа прокси/ошибки API не должен уходить в промпт картинки и на заглушку."""
    if not text or not str(text).strip():
        return True
    head = text.lstrip()[:500]
    if re.match(r'(?i)^HTTP/\d', head):
        return True
    if re.search(r'(?i)HTTP\s+Error\s+\d{3}', head[:200]):
        return True
    return False


def _coalesce_image_prompt(refined: str, base: str) -> str:
    r = (refined or '').strip()
    b = (base or '').strip()
    if _prompt_looks_like_http_glitch(r):
        logger.warning('Отброшен промпт, похожий на HTTP/транспортную ошибку; используется базовый промпт.')
        return b
    return r


@router.get('/ping')
async def ai_ping() -> dict[str, str]:
    return {'ok': True, 'build': AI_ROUTER_BUILD, 'generate_bouquet_auth': 'optional'}

STATIC_AI_DIR = Path(__file__).resolve().parents[4] / 'static' / 'ai'
BOUQUET_IMAGES_DIR = Path(__file__).resolve().parents[4] / 'static' / 'bouquets'


def _ensure_static_dir() -> None:
    STATIC_AI_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_bouquet_images_dir() -> None:
    BOUQUET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_expired_files(ttl_seconds: int) -> None:
    _ensure_static_dir()
    now = time.time()
    for p in STATIC_AI_DIR.glob('*.webp'):
        try:
            if now - p.stat().st_mtime > ttl_seconds:
                p.unlink(missing_ok=True)
        except Exception:
            # Best-effort cleanup only.
            continue


def _parse_rate_limit(value: str) -> tuple[int, int]:
    """
    Very small parser for "N/minute", "N/hour", "N/day", or plain "N".
    Returns (limit_count, window_seconds).
    """
    text = value.strip()
    if re.match(r'^\d+$', text):
        return max(1, int(text)), 86400

    m = re.match(r'^\s*(\d+)\s*/\s*(minute|hour|day)\s*$', text, flags=re.IGNORECASE)
    if not m:
        return 5, 86400
    count = int(m.group(1))
    unit = m.group(2).lower()
    if unit == 'minute':
        window = 60
    elif unit == 'hour':
        window = 3600
    else:
        window = 86400
    return max(1, count), window


# In-memory per-user limiter for image generation.
_user_image_calls: dict[int, list[float]] = {}


def _rate_limit_uid(request: Request, user: User | None) -> int:
    """Зарегистрированный пользователь — по id; гость — устойчивый отрицательный id по IP."""
    if user is not None:
        return user.id
    host = (request.client.host if request.client else '') or '0.0.0.0'
    xff = (request.headers.get('x-forwarded-for') or '').split(',')[0].strip()
    key = f'{host}|{xff}'
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    n = int(digest[:12], 16) % 2_000_000_000
    return -(n + 1)


def _enforce_user_limit(user_id: int) -> None:
    limit, window = _parse_rate_limit(settings.AI_IMAGES_RATE_LIMIT_PER_USER)
    now = time.time()
    calls = _user_image_calls.get(user_id, [])
    calls = [t for t in calls if now - t < window]
    if len(calls) >= limit:
        raise HTTPException(status_code=429, detail='Too many requests')
    calls.append(now)
    _user_image_calls[user_id] = calls


class FlowerQty(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    qty: int = Field(ge=1, le=200)


class AIGenerateRequest(BaseModel):
    flowers: list[FlowerQty] = Field(min_length=1, max_length=30)
    occasion: str | None = Field(default=None, max_length=120)
    palette: str | None = Field(default=None, max_length=120)
    budget_rub: int | None = Field(default=None, ge=0, le=1_000_000)
    wrap_type: str | None = Field(default=None, max_length=120)
    style: str = Field(default='реализм', max_length=80)


class AIFlowerPriceEstimate(BaseModel):
    """Оценка по одному виду из запроса: средняя цена за 1 шт. по всем строкам каталога с подходящим названием."""

    requested_name: str
    qty: int
    matched_catalog_items: int = 0
    avg_price_per_unit_rub: float | None = None
    line_subtotal_rub: float | None = None


class AIGenerateResponse(BaseModel):
    images: list[str]
    prompt: str
    expires_at: datetime
    estimated_total_rub: float | None = None
    price_breakdown: list[AIFlowerPriceEstimate] = Field(default_factory=list)
    price_note: str | None = Field(
        default=None,
        description='Краткое пояснение расчёта для клиента (не от LLM, по данным БД).',
    )


class AISnapshotForCartIn(BaseModel):
    """Сохранить сгенерированное изображение как личный букет (не в витрину) и получить id для корзины."""

    ai_image_path: str = Field(..., min_length=12, max_length=512)
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price: float = Field(..., ge=0, le=9_999_999)
    flowers: dict = Field(default_factory=dict)


def _parse_ai_webp_filename(image_path: str) -> str | None:
    p = (image_path or '').strip()
    m = re.match(r'^/api/v1/ai/images/([a-f0-9]{32}\.webp)$', p, flags=re.IGNORECASE)
    return m.group(1) if m else None


def _tokens_for_match(text: str) -> list[str]:
    return [t for t in re.split(r'[^a-zа-яё0-9]+', text.lower(), flags=re.IGNORECASE) if len(t) >= 2]


def _norm_match(s: str) -> str:
    return (s or '').replace('ё', 'е').lower().strip()


def _flower_catalog_blob(f: FlowerRow) -> str:
    parts = [f.name, f.latin_name or '', f.category or '', f.color or '']
    return _norm_match(' '.join(p for p in parts if p))


def _name_variants_for_occasion(name: str) -> set[str]:
    """Набор нормализованных вариантов для поиска в тексте (роза / розы / роз)."""
    n = _norm_match(name)
    if not n:
        return set()
    out: set[str] = {n}
    if len(n) >= 4 and n.endswith('а'):
        stem = n[:-1]
        out.update({stem + 'ы', stem + 'е', stem + 'ой', stem + 'ам', stem})
    if len(n) >= 4 and n.endswith('я'):
        stem = n[:-1]
        out.update({stem + 'и', stem + 'е', stem})
    if len(n) >= 5 and n.endswith('ие'):
        stem = n[:-2]
        out.update({stem + 'ия', stem + 'ий', stem})
    # «лилия» → лилии, лилий, лилиям…
    if 'лил' in n:
        out.update({'лилия', 'лилии', 'лилий', 'лилям', 'лилями', 'лил', 'лили'})
    if 'пион' in n:
        out.update({'пион', 'пионы', 'пиона', 'пионов'})
    if 'роз' in n:
        out.update({'роза', 'розы', 'роз', 'розам'})
    if 'тюльп' in n:
        out.update({'тюльпан', 'тюльпаны', 'тюльпана'})
    if 'хриз' in n:
        out.update({'хризантема', 'хризантемы', 'хризантем'})
    return {v for v in out if len(v) >= 2}


def _qty_before_keyword(compact: str, keyword: str) -> int | None:
    """Число слева или сразу справа от ключевого слова (…9лилий… или …лилий9штук…)."""
    if not compact or not keyword:
        return None
    idx = compact.find(keyword)
    if idx < 0:
        return None
    i = idx - 1
    left = ''
    while i >= 0 and compact[i].isdigit():
        left = compact[i] + left
        i -= 1
    if left:
        try:
            return max(1, min(200, int(left)))
        except ValueError:
            pass
    j = idx + len(keyword)
    right = ''
    while j < len(compact) and compact[j].isdigit():
        right += compact[j]
        j += 1
    if right:
        try:
            return max(1, min(200, int(right)))
        except ValueError:
            return None
    return None


def _compact_alpha_num(s: str) -> str:
    return re.sub(r'[^a-zа-яё0-9]+', '', _norm_match(s))


def _occasion_mentions_flower(occasion_norm: str, f: FlowerRow) -> bool:
    """Есть ли в свободном тексте запроса упоминание этого вида из каталога."""
    compact = _compact_alpha_num(occasion_norm)
    if len(compact) < 3:
        return False
    for variant in _name_variants_for_occasion(f.name):
        if len(variant) >= 3 and variant in compact:
            return True
    if f.latin_name:
        lat = _compact_alpha_num(f.latin_name)
        if len(lat) >= 4 and lat in compact:
            return True
    return False


def _flower_row_matches_request(request_name: str, f: FlowerRow) -> bool:
    blob = _flower_catalog_blob(f)
    rn = _norm_match(request_name)
    if not rn or not blob:
        return False
    blob_c = _compact_alpha_num(blob)
    if rn in blob or blob in rn:
        return True
    for t in _tokens_for_match(request_name):
        if len(t) >= 3 and t in blob:
            return True
        if len(t) >= 4 and t[:4] in blob_c:
            return True
    for t in _tokens_for_match(f'{f.name} {f.latin_name}'):
        if len(t) >= 3 and t in rn:
            return True
        if len(t) >= 4 and t[:4] in _compact_alpha_num(rn):
            return True
    return False


def _merge_flowers_for_pricing(payload: AIGenerateRequest, catalog: list[FlowerRow]) -> list[FlowerQty]:
    """
    Строки из payload + виды из каталога, явно упомянутые в occasion (если в payload были пустые/битые имена).
    Дубликаты по нормализованному имени из запроса схлопываем по количеству.
    """
    merged: dict[str, FlowerQty] = {}
    for line in payload.flowers:
        raw = (line.name or '').strip()
        if not raw or '[object' in raw.lower():
            continue
        key = _norm_match(raw)
        if not key:
            continue
        if key in merged:
            prev = merged[key]
            merged[key] = FlowerQty(name=prev.name, qty=min(200, prev.qty + line.qty))
        else:
            merged[key] = FlowerQty(name=raw, qty=line.qty)

    occ = (payload.occasion or '').strip()
    if occ:
        occ_n = _norm_match(occ)
        compact = _compact_alpha_num(occ_n)
        for f in catalog:
            fn_key = _norm_match(f.name)
            if len(fn_key) < 2:
                continue
            if fn_key in merged:
                continue
            if not _occasion_mentions_flower(occ_n, f):
                continue
            qty_guess = 1
            for variant in sorted(_name_variants_for_occasion(f.name), key=len, reverse=True):
                if len(variant) < 3:
                    continue
                q = _qty_before_keyword(compact, variant)
                if q is not None:
                    qty_guess = q
                    break
            merged[fn_key] = FlowerQty(name=f.name, qty=min(200, qty_guess))

    return list(merged.values()) if merged else list(payload.flowers)


def _catalog_price_estimate_for_bouquet(
    catalog: list[FlowerRow],
    flowers: list[FlowerQty],
) -> tuple[list[AIFlowerPriceEstimate], float | None, str | None]:
    """
    Для каждой позиции букета: средняя price_per_unit по всем цветам каталога, у которых название
    сопоставимо с запрошенным видом; итог = сумма (qty × средняя_цена).
    """
    breakdown: list[AIFlowerPriceEstimate] = []
    total = 0.0
    any_matched = False
    for line in flowers:
        matches = [f for f in catalog if _flower_row_matches_request(line.name, f)]
        n = len(matches)
        if n == 0:
            breakdown.append(
                AIFlowerPriceEstimate(
                    requested_name=line.name,
                    qty=line.qty,
                    matched_catalog_items=0,
                    avg_price_per_unit_rub=None,
                    line_subtotal_rub=None,
                )
            )
            continue
        prices = [float(f.price_per_unit) for f in matches]
        avg = float(statistics.mean(prices))
        sub = round(avg * line.qty, 2)
        any_matched = True
        total += sub
        breakdown.append(
            AIFlowerPriceEstimate(
                requested_name=line.name,
                qty=line.qty,
                matched_catalog_items=n,
                avg_price_per_unit_rub=round(avg, 2),
                line_subtotal_rub=sub,
            )
        )
    if not any_matched:
        note = 'Не удалось сопоставить состав с прайсом отдельных цветов — будет проверен каталог готовых букетов.'
        return breakdown, None, note
    total_r = round(total, 2)
    unmatched = [b.requested_name for b in breakdown if not b.matched_catalog_items]
    base_note = (
        f'Ориентировочно по прайсу цветов на сайте: около {int(round(total_r))} ₽ '
        '(цена за шт. из каталога «Цветы» × количество в запросе).'
    )
    if unmatched:
        tail = ' Без отдельной цены в прайсе: ' + ', '.join(unmatched[:5]) + ('…' if len(unmatched) > 5 else '') + '.'
        note = base_note + tail
    else:
        note = base_note
    return breakdown, total_r, note


def _bouquet_text_blob(b: BouquetRow) -> str:
    parts = [b.name or '', b.description or '']
    flowers = b.flowers if isinstance(b.flowers, dict) else {}
    for k in flowers.keys():
        if k != '_meta':
            parts.append(str(k))
    return _compact_alpha_num(_norm_match(' '.join(parts)))


def _score_bouquet_vs_request(
    b: BouquetRow, payload: AIGenerateRequest, flowers_for_price: list[FlowerQty]
) -> int:
    blob = _bouquet_text_blob(b)
    if len(blob) < 4:
        return 0
    hay = _compact_alpha_num(_norm_match(' '.join([payload.occasion or ''] + [x.name for x in flowers_for_price])))
    if len(hay) < 3:
        return 0
    score = 0
    for v in _name_variants_for_occasion(b.name):
        if len(v) >= 3 and v in hay:
            score += 4
    blob_words = _norm_match((b.name or '') + ' ' + (b.description or ''))
    for t in _tokens_for_match(payload.occasion or ''):
        if len(t) >= 4 and t in blob_words:
            score += 2
    if isinstance(b.flowers, dict):
        for k in b.flowers:
            if k == '_meta':
                continue
            for v in _name_variants_for_occasion(str(k)):
                if len(v) >= 3 and v in hay:
                    score += 5
    for line in flowers_for_price:
        for v in _name_variants_for_occasion(line.name):
            if len(v) >= 3 and v in blob:
                score += 5
    return score


def _pick_reference_bouquet(
    bouquets: list[BouquetRow], payload: AIGenerateRequest, flowers_for_price: list[FlowerQty]
) -> BouquetRow | None:
    scored: list[tuple[int, BouquetRow]] = []
    for b in bouquets:
        if not b.is_published:
            continue
        sc = _score_bouquet_vs_request(b, payload, flowers_for_price)
        if sc > 0:
            scored.append((sc, b))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    best = scored[0][0]
    top = [b for s, b in scored if s == best]
    prices = sorted(float(x.price) for x in top)
    mid = prices[len(prices) // 2]
    for b in top:
        if float(b.price) == mid:
            return b
    return top[0]


def _apply_bouquet_catalog_fallback(
    bouquets: list[BouquetRow],
    payload: AIGenerateRequest,
    flowers_for_price: list[FlowerQty],
    breakdown: list[AIFlowerPriceEstimate],
    *,
    flower_total: float | None,
    flower_note: str | None,
) -> tuple[list[AIFlowerPriceEstimate], float | None, str | None]:
    if flower_total is not None and flower_total > 0:
        return breakdown, flower_total, flower_note
    ref = _pick_reference_bouquet(bouquets, payload, flowers_for_price)
    if ref is None:
        fail = 'Не удалось оценить стоимость: нет совпадений с каталогом цветов и с опубликованными букетами на сайте.'
        return breakdown, None, fail
    price = float(ref.price)
    ref_name = (ref.name or 'Букет').strip()[:120]
    bd = [
        AIFlowerPriceEstimate(
            requested_name=ref_name,
            qty=1,
            matched_catalog_items=1,
            avg_price_per_unit_rub=round(price, 2),
            line_subtotal_rub=round(price, 2),
        )
    ]
    short = (
        f'Ориентировочно по цене похожего букета в каталоге: около {int(round(price))} ₽ '
        f'(карточка «{ref_name}»; состав и детали — в описании товара на сайте).'
    )
    return bd, price, short


async def _load_catalog_for_pricing(db: AsyncSession) -> list[FlowerRow]:
    return await flower_crud.list(db, offset=0, limit=10_000, query=None, category=None)


def _require_openai_configured() -> None:
    if not settings.OPENAI_API_KEY or not str(settings.OPENAI_API_KEY).strip():
        raise HTTPException(status_code=500, detail='OPENAI_API_KEY is not set')


def _gigachat_basic_secret() -> str:
    """
    Значение для Authorization: Basic <secret>.
    В кабинете GigaChat обычно копируют готовую base64-строку; либо задайте CLIENT_ID и CLIENT_SECRET.
    """
    if settings.GIGACHAT_AUTHORIZATION_KEY and str(settings.GIGACHAT_AUTHORIZATION_KEY).strip():
        s = str(settings.GIGACHAT_AUTHORIZATION_KEY).strip()
        if s.lower().startswith('basic '):
            s = s[6:].strip()
        return s
    cid = (settings.GIGACHAT_CLIENT_ID or '').strip()
    csec = (settings.GIGACHAT_CLIENT_SECRET or '').strip()
    if cid and csec:
        return base64.b64encode(f'{cid}:{csec}'.encode('utf-8')).decode('ascii')
    raise HTTPException(
        status_code=500,
        detail='GigaChat: укажите GIGACHAT_AUTHORIZATION_KEY или пару GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET в Backend/.env',
    )


_gigachat_access_token: str | None = None
_gigachat_token_deadline: float = 0.0


async def _gigachat_obtain_access_token(client: httpx.AsyncClient) -> str:
    global _gigachat_access_token, _gigachat_token_deadline
    now = time.time()
    if _gigachat_access_token and now < _gigachat_token_deadline - 30:
        return _gigachat_access_token

    secret = _gigachat_basic_secret()
    r = await client.post(
        settings.GIGACHAT_OAUTH_URL,
        headers={
            'Authorization': f'Basic {secret}',
            'RqUID': str(uuid.uuid4()),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data={'scope': settings.GIGACHAT_SCOPE},
    )
    if r.status_code >= 400:
        logger.warning('GigaChat OAuth error status=%s body=%s', r.status_code, r.text[:1200])
        raise HTTPException(status_code=502, detail=f'GigaChat OAuth error: {r.status_code}')

    data = r.json()
    token = data.get('access_token')
    if not token:
        raise HTTPException(status_code=502, detail='GigaChat OAuth: no access_token')

    exp = data.get('expires_at')
    if isinstance(exp, (int, float)) and exp > 1_000_000_000_000:
        _gigachat_token_deadline = float(exp) / 1000.0
    else:
        _gigachat_token_deadline = now + float(data.get('expires_in', 25 * 60))

    _gigachat_access_token = token
    return token


async def _gigachat_refine_image_prompt(client: httpx.AsyncClient, base_prompt: str, *, price_note_ru: str | None = None) -> str:
    """
    Уточняет промпт для генерации изображения (GigaChat не отдаёт готовые фото — только текст).
    """
    token = await _gigachat_obtain_access_token(client)
    system = (
        'Ты помощник флориста. По входным требованиям составь ОДИН цельный промпт на английском языке '
        'для нейросети генерации изображений (фотореализм, студийное фото букета в вазе, белый фон, '
        'упаковка и лента, без людей, рук, логотипов и текста). Только текст промпта, без пояснений.'
    )
    extra = ''
    if price_note_ru:
        pn = price_note_ru.strip()
        if len(pn) > 400:
            pn = pn[:400] + '…'
        extra = f'\n\nДля справки (не выдумывай другие суммы): {pn}'
    user_msg = f'Исходные данные для букета:\n{base_prompt}{extra}'
    body = {
        'model': settings.GIGACHAT_MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_msg},
        ],
        'temperature': 0.35,
        'max_tokens': 1200,
    }
    r = await client.post(
        settings.GIGACHAT_API_URL,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json=body,
    )
    if r.status_code >= 400:
        logger.warning('GigaChat chat error status=%s body=%s', r.status_code, r.text[:1200])
        raise HTTPException(status_code=502, detail=f'GigaChat API error: {r.status_code}')

    payload = r.json()
    choices = payload.get('choices') or []
    if not choices:
        raise HTTPException(status_code=502, detail='GigaChat: empty choices')
    content = (choices[0].get('message') or {}).get('content') or ''
    text = str(content).strip()
    if len(text) < 20:
        return base_prompt
    if len(text) > 3800:
        text = text[:3800] + '…'
    return text


def _gigachat_api_v1_base() -> str:
    url = (settings.GIGACHAT_API_URL or '').rstrip('/')
    if url.endswith('/chat/completions'):
        return url[: -len('/chat/completions')]
    return 'https://gigachat.devices.sberbank.ru/api/v1'


def _extract_image_file_id_from_message(content: str) -> str | None:
    if not content:
        return None
    m = re.search(r'<img[^>]+src=["\']([0-9a-fA-F-]{36})["\']', content, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r'\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b', content)
    return m2.group(1) if m2 else None


async def _gigachat_download_image_bytes(client: httpx.AsyncClient, token: str, file_id: str) -> bytes:
    url = f'{_gigachat_api_v1_base()}/files/{file_id}/content'
    r = await client.get(
        url,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/jpg',
        },
    )
    if r.status_code >= 400:
        logger.warning('GigaChat file download failed status=%s body=%s', r.status_code, r.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f'GigaChat: не удалось скачать файл изображения (HTTP {r.status_code})',
        )
    return r.content


def _gigachat_kandinsky_user_message(prompt: str, *, short: bool) -> str:
    """Короткий запрос в духе официальных примеров Сбера лучше запускает text2image."""
    p = (prompt or '').strip()
    if len(p) > 1200:
        p = p[:1200] + '…'
    if short:
        return (
            'Нарисуй фотореалистичное студийное фото букета цветов в прозрачной вазе, белый фон, '
            'без людей и без текста на картинке. Кратко пожелания: '
            + p[:500]
        )
    return (
        'Нарисуй одно изображение (студийное фото товара): букет в вазе, светлый фон, без людей и без текста. '
        'Детали: '
        + p
    )


async def _gigachat_kandinsky_one_image(client: httpx.AsyncClient, prompt: str) -> bytes:
    """
    Генерация одного изображения через встроенную функцию text2image (Kandinsky) в GigaChat API.
    См. https://developers.sber.ru/docs/ru/gigachat/api/images-generation
    """
    token = await _gigachat_obtain_access_token(client)

    async def _post_chat(user_content: str) -> httpx.Response:
        body = {
            'model': settings.GIGACHAT_MODEL,
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'Ты помощник каталога цветов. На запросы «нарисуй» вызывай генерацию изображения (text2image).'
                    ),
                },
                {'role': 'user', 'content': user_content},
            ],
            'function_call': 'auto',
        }
        return await client.post(
            settings.GIGACHAT_API_URL,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            json=body,
        )

    last_content = ''
    for short in (False, True):
        ru_prompt = _gigachat_kandinsky_user_message(prompt, short=short)
        r = await _post_chat(ru_prompt)
        if r.status_code >= 400:
            logger.warning('GigaChat text2image error status=%s body=%s', r.status_code, r.text[:1200])
            raise HTTPException(
                status_code=502,
                detail=f'GigaChat (Kandinsky): ошибка запроса генерации изображения: {r.status_code} {r.text[:500]}',
            )
        try:
            payload = r.json()
        except ValueError as je:
            logger.warning('GigaChat text2image: ответ не JSON, status=%s body=%s', r.status_code, r.text[:800])
            raise HTTPException(
                status_code=502,
                detail=(
                    'GigaChat вернул не-JSON (часто из-за SSL/прокси). '
                    'Попробуйте в Backend/.env: GIGACHAT_SSL_VERIFY=false для отладки. '
                    f'Фрагмент ответа: {r.text[:400]!r}'
                ),
            ) from je
        choices = payload.get('choices') or []
        if not choices:
            continue
        msg_content = (choices[0].get('message') or {}).get('content')
        content = str(msg_content or '')
        last_content = content
        file_id = _extract_image_file_id_from_message(content)
        if file_id:
            return await _gigachat_download_image_bytes(client, token, file_id)

    raise HTTPException(
        status_code=502,
        detail=(
            'GigaChat не вернул изображение (нет тега <img src="uuid"> в ответе). '
            'Убедитесь, что у проекта включена генерация изображений и модель поддерживает text2image. '
            'Последний ответ модели: '
            + (last_content[:900] if last_content else '(пусто)')
        ),
    )


async def _gigachat_generate_kandinsky_images(client: httpx.AsyncClient, prompt: str, count: int) -> list[bytes]:
    n = max(1, min(10, int(count)))
    out: list[bytes] = []
    for i in range(n):
        variant = prompt if n == 1 else f'{prompt}\n(Вариант оформления {i + 1} из {n}.)'
        out.append(await _gigachat_kandinsky_one_image(client, variant))
    return out


MINIMAL_OPENAI_PROMPT = (
    'Professional studio product photograph of a fresh flower bouquet in a clear glass vase, '
    'elegant wrapping paper and satin ribbon, pure white seamless background, soft diffused '
    'light, photorealistic detail. No people, no hands, no logos, no text.'
)


def _build_prompt(
    payload: AIGenerateRequest,
    *,
    catalog_price_hint: str | None = None,
    flowers_line: list[FlowerQty] | None = None,
) -> str:
    fl = flowers_line if flowers_line else payload.flowers
    flowers = ', '.join([f'{x.name} x{x.qty}' for x in fl])
    parts = [
        'Photorealistic studio product photo of a fresh flower bouquet arrangement.',
        f'Flowers: {flowers}.',
        'The bouquet must be wrapped with elegant packaging paper and a ribbon bow.',
        'Place the bouquet in a vase.',
        'Background: pure white seamless studio background.',
        'Lighting: soft studio lighting, high detail, realistic textures.',
        'No people, no hands, no logos, no text, no watermark, no brand marks.',
    ]
    if payload.occasion:
        occ = payload.occasion.strip()
        if len(occ) > 400:
            occ = occ[:400] + '…'
        parts.append(f'Occasion / customer wishes: {occ}.')
    if payload.palette:
        parts.append(f'Color palette: {payload.palette}.')
    if payload.wrap_type:
        parts.append(f'Wrap type: {payload.wrap_type}.')
    if payload.budget_rub is not None:
        parts.append(f'Budget: around {payload.budget_rub} RUB.')
    if payload.style:
        parts.append(f'Style: {payload.style}.')
    if catalog_price_hint:
        parts.append(catalog_price_hint)
    full = ' '.join(parts)
    if len(full) > 3800:
        full = full[:3800] + '…'
    return full


async def _openai_item_to_bytes(client: httpx.AsyncClient, item: dict) -> bytes:
    b64 = item.get('b64_json')
    if b64:
        return base64.b64decode(b64)
    img_url = item.get('url')
    if img_url:
        r = await client.get(img_url, follow_redirects=True)
        if r.status_code >= 400:
            logger.warning('OpenAI image URL fetch failed status=%s', r.status_code)
            raise HTTPException(status_code=502, detail='OpenAI image download failed')
        return r.content
    raise HTTPException(status_code=502, detail='OpenAI returned no image data')


async def _generate_images_openai(prompt: str, *, count: int) -> list[bytes]:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail='AI is not configured')

    url = 'https://api.openai.com/v1/images/generations'
    headers = {
        'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    model = (settings.OPENAI_IMAGE_MODEL or 'dall-e-3').strip()
    n = max(1, min(10, int(count)))

    async def _post_images(client: httpx.AsyncClient, body: dict) -> httpx.Response:
        return await client.post(url, json=body, headers=headers)

    async def _one_dalle3(client: httpx.AsyncClient, use_prompt: str) -> bytes:
        body = {
            'model': 'dall-e-3',
            'prompt': use_prompt,
            'n': 1,
            'size': '1024x1024',
            'response_format': 'b64_json',
        }
        r = await _post_images(client, body)
        if r.status_code >= 400:
            logger.warning('OpenAI images error status=%s body=%s', r.status_code, r.text[:1200])
            # Не пробрасываем 401/403 провайдера как HTTP 401 — фронт путает с JWT.
            upstream = r.status_code if r.status_code < 500 else 502
            if upstream in (401, 403):
                upstream = 502
            raise HTTPException(status_code=upstream, detail=f'OpenAI error: {r.text[:500]}')
        data = r.json()
        items = data.get('data') or []
        if not items:
            raise HTTPException(status_code=502, detail='OpenAI returned no image')
        return await _openai_item_to_bytes(client, items[0])

    async def _batch_dalle2(client: httpx.AsyncClient, use_prompt: str) -> list[bytes]:
        body = {
            'model': 'dall-e-2',
            'prompt': use_prompt,
            'n': n,
            'size': '1024x1024',
            'response_format': 'b64_json',
        }
        r = await _post_images(client, body)
        if r.status_code >= 400:
            logger.warning('OpenAI images error status=%s body=%s', r.status_code, r.text[:1200])
            # Не пробрасываем 401/403 провайдера как HTTP 401 — фронт путает с JWT.
            upstream = r.status_code if r.status_code < 500 else 502
            if upstream in (401, 403):
                upstream = 502
            raise HTTPException(status_code=upstream, detail=f'OpenAI error: {r.text[:500]}')
        data = r.json()
        items = data.get('data') or []
        out: list[bytes] = []
        for it in items[:n]:
            out.append(await _openai_item_to_bytes(client, it))
        if not out:
            raise HTTPException(status_code=502, detail='OpenAI returned no images')
        return out

    async def _run_dalle3_sequential(client: httpx.AsyncClient, use_prompt: str) -> list[bytes]:
        # Sequential requests avoid org-level rate limits on parallel image jobs.
        out: list[bytes] = []
        for _ in range(n):
            out.append(await _one_dalle3(client, use_prompt))
        return out

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            if model == 'dall-e-3':
                return await _run_dalle3_sequential(client, prompt)
            return await _batch_dalle2(client, prompt)
        except HTTPException as first_err:
            if first_err.status_code == 400 and prompt != MINIMAL_OPENAI_PROMPT:
                logger.warning('OpenAI rejected prompt; retrying with minimal prompt')
                if model == 'dall-e-3':
                    return await _run_dalle3_sequential(client, MINIMAL_OPENAI_PROMPT)
                return await _batch_dalle2(client, MINIMAL_OPENAI_PROMPT)
            raise


def _to_webp(img_bytes: bytes, *, size: tuple[int, int] = (1024, 1024)) -> bytes:
    im = Image.open(BytesIO(img_bytes)).convert('RGB')
    if im.size != size:
        im = im.resize(size)
    out = BytesIO()
    im.save(out, format='WEBP', quality=92, method=6)
    return out.getvalue()


def _generate_fallback_webp(prompt: str, *, size: tuple[int, int] = (1024, 1024), index: int = 1) -> bytes:
    """
    Local fallback image if provider is temporarily unavailable.
    Не подставляем сырой текст ошибок HTTP/прокси в подпись к картинке.
    """
    im = Image.new('RGB', size, color=(245, 247, 251))
    draw = ImageDraw.Draw(im)

    # Minimal visual placeholder with bouquet-like circles.
    draw.rectangle((40, 40, size[0] - 40, size[1] - 40), outline=(180, 190, 220), width=3)
    draw.ellipse((360, 180, 660, 480), fill=(255, 214, 228), outline=(215, 120, 170), width=3)
    draw.ellipse((290, 220, 510, 440), fill=(206, 229, 255), outline=(100, 150, 220), width=3)
    draw.ellipse((510, 240, 730, 460), fill=(224, 246, 210), outline=(130, 180, 120), width=3)
    draw.rectangle((430, 470, 590, 760), fill=(240, 230, 210), outline=(170, 150, 120), width=3)

    flat = ' '.join((prompt or '').split())
    safe_hint = ''
    if flat and not _prompt_looks_like_http_glitch(flat[:400]):
        safe_hint = (flat[:100] + ('…' if len(flat) > 100 else '')).strip()
    draw.text((80, 760), f'Заглушка #{index}', fill=(35, 45, 65))
    draw.text((80, 810), 'Генерация недоступна (сеть или ключ API).', fill=(80, 90, 110))
    draw.text((80, 860), 'Режим openai: ключ OpenAI. Режим gigachat: ключ GigaChat в .env', fill=(80, 90, 110))
    if safe_hint:
        draw.text((80, 920), safe_hint, fill=(80, 90, 110))

    out = BytesIO()
    im.save(out, format='WEBP', quality=90, method=6)
    return out.getvalue()


@router.post('/generate-bouquet', response_model=AIGenerateResponse)
async def generate_bouquet(
    request: Request,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> AIGenerateResponse:
    _enforce_user_limit(_rate_limit_uid(request, current_user))

    ttl_seconds = int(settings.AI_IMAGES_TTL_HOURS) * 3600
    _cleanup_expired_files(ttl_seconds)

    catalog = await _load_catalog_for_pricing(db)
    bouquets = await bouquet_crud.list(db, offset=0, limit=400, query=None, published_only=True)
    flowers_for_price = _merge_flowers_for_pricing(payload, catalog)
    bd0, est0, note0 = _catalog_price_estimate_for_bouquet(catalog, flowers_for_price)
    breakdown, estimated_total, price_note = _apply_bouquet_catalog_fallback(
        bouquets, payload, flowers_for_price, bd0, flower_total=est0, flower_note=note0
    )
    catalog_price_hint = None
    if estimated_total is not None:
        catalog_price_hint = (
            'Approximate catalog stem cost (average database price per flower type × quantity): '
            f'about {int(round(estimated_total))} RUB.'
        )

    base_prompt = _build_prompt(
        payload, catalog_price_hint=catalog_price_hint, flowers_line=flowers_for_price or None
    )
    _ensure_static_dir()
    urls: list[str] = []

    provider = (settings.AI_IMAGE_PROVIDER or 'openai').strip().lower()
    if provider not in {'openai', 'gigachat'}:
        raise HTTPException(status_code=500, detail='Invalid AI_IMAGE_PROVIDER (use openai or gigachat)')

    prompt_for_images = base_prompt
    generated_webps: list[bytes] = []

    if provider == 'gigachat':
        try:
            async with httpx.AsyncClient(timeout=300.0, verify=settings.GIGACHAT_SSL_VERIFY) as gc:
                refined = await _gigachat_refine_image_prompt(gc, base_prompt, price_note_ru=price_note)
                prompt_for_images = _coalesce_image_prompt(refined, base_prompt)
                raw_images = await _gigachat_generate_kandinsky_images(
                    gc, prompt_for_images, int(settings.AI_IMAGES_COUNT)
                )
            generated_webps = []
            for idx, raw in enumerate(raw_images[: int(settings.AI_IMAGES_COUNT)]):
                try:
                    generated_webps.append(_to_webp(raw, size=(1024, 1024)))
                except Exception as pil_e:
                    logger.exception('PIL/WEBP: кадр %s', idx)
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            'GigaChat отдал файл, но он не распознан как изображение (возможен неверный ответ вместо JPG). '
                            f'Ошибка: {pil_e!s}'
                        ),
                    ) from pil_e
        except HTTPException as he:
            # В access-логе uvicorn видно только "502"; сюда пишем ту же причину, что уходит в JSON detail.
            _d = he.detail
            _ds = _d if isinstance(_d, str) else str(_d)
            logger.error('ai/generate-bouquet (gigachat) → HTTP %s: %s', he.status_code, _ds[:2500])
            raise
        except Exception as e:
            logger.exception('GigaChat/Kandinsky image pipeline')
            hint = ''
            es = str(e).lower()
            if 'certificate' in es or 'ssl' in es or 'tls' in es:
                hint = (
                    ' Похоже на проблему SSL с сертификатом Сбера: в Backend/.env установите GIGACHAT_SSL_VERIFY=false '
                    '(только для локальной отладки).'
                )
            elif 'connect' in es or 'unreachable' in es or 'timed out' in es:
                hint = ' Проверьте сеть, файрвол и доступность gigachat.devices.sberbank.ru.'
            raise HTTPException(
                status_code=502,
                detail=(
                    'GigaChat (Kandinsky): '
                    + (str(e)[:1200] if str(e) else repr(e))
                    + hint
                    + ' Если ключ верный — пришлите этот текст поддержке или проверьте лимиты проекта на developers.sber.ru.'
                ),
            ) from e
    else:
        _require_openai_configured()
        prompt_for_images = base_prompt
        try:
            raw_images = await _generate_images_openai(prompt_for_images, count=settings.AI_IMAGES_COUNT)
            generated_webps = [_to_webp(raw, size=(1024, 1024)) for raw in raw_images[: settings.AI_IMAGES_COUNT]]
        except HTTPException as gen_err:
            if gen_err.status_code in {400, 401, 403, 429}:
                logger.warning('OpenAI image generation user error: %s', gen_err.detail)
                raise gen_err
            d = str(gen_err.detail or '')
            if 'OpenAI' in d or 'openai' in d.lower():
                raise HTTPException(
                    status_code=502,
                    detail=(
                        'Не удалось сгенерировать изображение через OpenAI. Проверьте OPENAI_API_KEY в Backend/.env, '
                        'баланс и лимиты на https://platform.openai.com/api-keys. Техническая информация: '
                        + d[:400]
                    ),
                ) from gen_err
            logger.warning('OpenAI image generation failed, using placeholder: %s', gen_err.detail)
            generated_webps = [
                _generate_fallback_webp(prompt_for_images, size=(1024, 1024), index=i + 1)
                for i in range(max(1, int(settings.AI_IMAGES_COUNT)))
            ]
        except Exception:
            logger.exception('Unexpected error during OpenAI image pipeline')
            generated_webps = [
                _generate_fallback_webp(prompt_for_images, size=(1024, 1024), index=i + 1)
                for i in range(max(1, int(settings.AI_IMAGES_COUNT)))
            ]

    for webp in generated_webps:
        name = f'{uuid.uuid4().hex}.webp'
        path = STATIC_AI_DIR / name
        path.write_bytes(webp)
        urls.append(f'{settings.API_V1_STR}/ai/images/{name}')

    expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = expires_at.__class__.fromtimestamp(expires_at.timestamp() + ttl_seconds, tz=timezone.utc)
    return AIGenerateResponse(
        images=urls,
        prompt=prompt_for_images,
        expires_at=expires_at,
        estimated_total_rub=estimated_total,
        price_breakdown=breakdown,
        price_note=price_note,
    )


@router.post('/snapshot-for-cart', response_model=BouquetRead, status_code=201)
async def snapshot_ai_bouquet_for_cart(
    body: AISnapshotForCartIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BouquetRead:
    """
    Копирует webp из временной папки AI в постоянную папку букетов и создаёт запись Bouquet (is_published=false).
    """
    fname = _parse_ai_webp_filename(body.ai_image_path)
    if not fname:
        raise HTTPException(status_code=400, detail='Некорректный путь к изображению AI (ожидается /api/v1/ai/images/<id>.webp)')
    src = STATIC_AI_DIR / fname
    if not src.is_file():
        raise HTTPException(status_code=404, detail='Файл изображения не найден или срок хранения истёк')
    _ensure_bouquet_images_dir()
    dest_name = f'{uuid.uuid4().hex}.webp'
    dest = BOUQUET_IMAGES_DIR / dest_name
    shutil.copy2(src, dest)
    image_url = f'{settings.API_V1_STR}/bouquets/images/{dest_name}'
    flowers_payload = body.flowers if isinstance(body.flowers, dict) else {}
    bouquet_in = BouquetCreate(
        name=body.name.strip()[:160],
        description=(body.description or '').strip()[:2000] or None,
        price=float(body.price),
        flowers=flowers_payload,
        image_url=image_url,
        is_published=False,
    )
    bouquet = await bouquet_crud.create(db, bouquet_in, current_user.id)
    return bouquet


@router.get('/images/{name}')
async def get_generated_image(
    name: str,
    request: Request,
) -> FileResponse:
    _ = request
    _ensure_static_dir()

    # Basic traversal protection.
    if '/' in name or '\\' in name:
        raise HTTPException(status_code=400, detail='Invalid name')
    path = STATIC_AI_DIR / name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail='Not found')

    ttl_seconds = int(settings.AI_IMAGES_TTL_HOURS) * 3600
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=404, detail='Not found')

    return FileResponse(path=str(path), media_type='image/webp')


@router.get('/flowers', response_model=list[Flower])
async def ai_flowers(
    db: AsyncSession = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
) -> list[Flower]:
    return await flower_crud.list(db, offset=offset, limit=limit)
