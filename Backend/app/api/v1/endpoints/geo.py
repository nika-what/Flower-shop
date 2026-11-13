"""Проверка адреса доставки в границах Новосибирска через внешний геокодер."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas.geo import AddressSuggestOut, AddressValidateIn, AddressValidateOut

router = APIRouter(prefix='/geo', tags=['geo'])
logger = logging.getLogger(__name__)

# Примерный bbox Новосибирска (min_lon, min_lat, max_lon, max_lat) — отсекает другие города области.
NSK_BBOX = (82.55, 54.78, 83.35, 55.18)

YANDEX_GEOCODE_URL = 'https://geocode-maps.yandex.ru/1.x/'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'


def _query_with_city(raw: str) -> str:
    s = raw.strip()
    low = s.lower()
    if 'новосибирск' in low:
        return s
    return f'Новосибирск, {s}'


def _in_nsk_bbox(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = NSK_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _yandex_locality_is_nsk(components: list[dict[str, Any]] | None) -> bool:
    if not components:
        return False
    for c in components:
        if c.get('kind') == 'locality' and c.get('name'):
            name = str(c['name']).lower()
            if 'новосибирск' in name:
                return True
    return False


def _parse_yandex_point(pos: str | None) -> tuple[float, float] | None:
    if not pos:
        return None
    parts = str(pos).strip().split()
    if len(parts) != 2:
        return None
    try:
        lon, lat = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    return lon, lat


async def _validate_yandex(address: str) -> AddressValidateOut | None:
    key = settings.YANDEX_GEOCODER_API_KEY
    if not key or not str(key).strip():
        return None
    q = _query_with_city(address)
    params = {'apikey': key.strip(), 'geocode': q, 'format': 'json', 'results': 5}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(YANDEX_GEOCODE_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        logger.warning('Yandex geocoder HTTP error: %s', e)
        raise HTTPException(status_code=502, detail='Сервис геокодирования временно недоступен') from e

    coll = data.get('response', {}).get('GeoObjectCollection', {})
    members = coll.get('featureMember') or []
    if not members:
        return AddressValidateOut(
            ok=False,
            message='Адрес не найден. Укажите улицу и дом в Новосибирске.',
        )

    best = members[0].get('GeoObject') or {}
    meta = (best.get('metaDataProperty') or {}).get('GeocoderMetaData') or {}
    addr_meta = meta.get('Address') or {}
    formatted = addr_meta.get('formatted')
    components = addr_meta.get('Components')
    pos = _parse_yandex_point((best.get('Point') or {}).get('pos'))

    if not formatted:
        return AddressValidateOut(ok=False, message='Адрес не распознан.')

    if not _yandex_locality_is_nsk(components if isinstance(components, list) else None):
        return AddressValidateOut(
            ok=False,
            message='Доставка только по Новосибирску. Укажите адрес в черте города.',
        )

    if pos and not _in_nsk_bbox(pos[0], pos[1]):
        return AddressValidateOut(
            ok=False,
            message='Точка на карте вне зоны доставки по Новосибирску.',
        )

    return AddressValidateOut(ok=True, normalized_address=str(formatted), message='Адрес подтверждён.')


async def _suggest_yandex(query: str) -> list[str] | None:
    key = settings.YANDEX_GEOCODER_API_KEY
    if not key or not str(key).strip():
        return None
    q = _query_with_city(query)
    params = {'apikey': key.strip(), 'geocode': q, 'format': 'json', 'results': 8}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(YANDEX_GEOCODE_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        logger.warning('Yandex geocoder suggest HTTP error: %s', e)
        raise HTTPException(status_code=502, detail='Сервис геокодирования временно недоступен') from e

    coll = data.get('response', {}).get('GeoObjectCollection', {})
    members = coll.get('featureMember') or []
    out: list[str] = []
    seen: set[str] = set()
    for m in members:
        best = m.get('GeoObject') or {}
        meta = (best.get('metaDataProperty') or {}).get('GeocoderMetaData') or {}
        addr_meta = meta.get('Address') or {}
        formatted = addr_meta.get('formatted')
        if not formatted:
            continue
        components = addr_meta.get('Components')
        if not _yandex_locality_is_nsk(components if isinstance(components, list) else None):
            continue
        pos = _parse_yandex_point((best.get('Point') or {}).get('pos'))
        if pos and not _in_nsk_bbox(pos[0], pos[1]):
            continue
        fs = str(formatted)
        if fs not in seen:
            seen.add(fs)
            out.append(fs)
        if len(out) >= 8:
            break
    return out


def _nominatim_row_ok_nsk(row: dict[str, Any]) -> bool:
    lat_s, lon_s = row.get('lat'), row.get('lon')
    if lat_s is None or lon_s is None:
        return False
    try:
        lat, lon = float(lat_s), float(lon_s)
    except (TypeError, ValueError):
        return False
    addr = row.get('address') or {}
    city = (
        addr.get('city')
        or addr.get('town')
        or addr.get('municipality')
        or addr.get('city_district')
        or ''
    )
    city_l = str(city).lower()
    display = row.get('display_name') or ''
    if 'новосибирск' not in city_l and 'новосибирск' not in display.lower():
        return False
    if not _in_nsk_bbox(lon, lat):
        return False
    return True


async def _suggest_nominatim(query: str) -> list[str]:
    q = _query_with_city(query)
    headers = {
        'User-Agent': f'FloristShop/1.0 ({settings.SMTP_FROM})',
        'Accept-Language': 'ru',
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            rows = await _nominatim_search(client, q, bounded=True)
            if not rows:
                rows = await _nominatim_search(client, q, bounded=False)
    except httpx.HTTPError as e:
        logger.warning('Nominatim suggest HTTP error: %s', e)
        raise HTTPException(status_code=502, detail='Сервис геокодирования временно недоступен') from e

    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _nominatim_row_ok_nsk(row):
            continue
        display = str(row.get('display_name') or '').strip()
        if not display or display in seen:
            continue
        seen.add(display)
        out.append(display)
        if len(out) >= 8:
            break
    return out


async def _nominatim_search(client: httpx.AsyncClient, q: str, bounded: bool) -> list[Any]:
    params: dict[str, str | int] = {
        'q': q,
        'format': 'json',
        'limit': 8,
        'addressdetails': 1,
        'countrycodes': 'ru',
    }
    if bounded:
        params['viewbox'] = f'{NSK_BBOX[0]},{NSK_BBOX[3]},{NSK_BBOX[2]},{NSK_BBOX[1]}'
        params['bounded'] = 1
    r = await client.get(NOMINATIM_URL, params=params)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


async def _validate_nominatim(address: str) -> AddressValidateOut:
    q = _query_with_city(address)
    headers = {
        'User-Agent': f'FloristShop/1.0 ({settings.SMTP_FROM})',
        'Accept-Language': 'ru',
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            rows = await _nominatim_search(client, q, bounded=True)
            if not rows:
                rows = await _nominatim_search(client, q, bounded=False)
    except httpx.HTTPError as e:
        logger.warning('Nominatim HTTP error: %s', e)
        raise HTTPException(status_code=502, detail='Сервис геокодирования временно недоступен') from e

    if not rows:
        return AddressValidateOut(
            ok=False,
            message='Адрес не найден. Укажите улицу и дом в Новосибирске.',
        )

    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _nominatim_row_ok_nsk(row):
            continue
        display = row.get('display_name') or ''
        return AddressValidateOut(
            ok=True,
            normalized_address=str(display),
            message='Адрес подтверждён.',
        )

    return AddressValidateOut(
        ok=False,
        message='Доставка только по Новосибирску. Укажите адрес в черте города.',
    )


@router.post('/validate-address', response_model=AddressValidateOut)
async def validate_address(body: AddressValidateIn) -> AddressValidateOut:
    """Проверяет, что строка адреса находится в Новосибирске (геокодер + bbox)."""
    yandex_result = await _validate_yandex(body.address)
    if yandex_result is not None:
        return yandex_result
    return await _validate_nominatim(body.address)


@router.get('/suggest-address', response_model=AddressSuggestOut)
async def suggest_address(q: str = Query('', max_length=400)) -> AddressSuggestOut:
    """Подсказки адресов в Новосибирске по частичной строке (для автодополнения)."""
    query = (q or '').strip()
    if len(query) < 2:
        return AddressSuggestOut(suggestions=[])
    yandex_s = await _suggest_yandex(query)
    if yandex_s is not None:
        return AddressSuggestOut(suggestions=yandex_s)
    return AddressSuggestOut(suggestions=await _suggest_nominatim(query))
