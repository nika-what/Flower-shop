from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.crud.bouquet import bouquet_crud
from app.models.user import User
from app.schemas.bouquet import Bouquet, BouquetCreate, BouquetUpdate

router = APIRouter(prefix='/bouquets', tags=['bouquets'])
BOUQUET_IMAGES_DIR = Path(__file__).resolve().parents[4] / 'static' / 'bouquets'


def _ensure_images_dir() -> None:
    BOUQUET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


@router.get('', response_model=list[Bouquet])
async def list_bouquets(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    query: str | None = None,
    published_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[Bouquet]:
    return await bouquet_crud.list(db, offset=offset, limit=limit, query=query, published_only=published_only)


@router.post('', response_model=Bouquet, status_code=201)
async def create_bouquet(
    bouquet_in: BouquetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Bouquet:
    return await bouquet_crud.create(db, bouquet_in, current_user.id)


@router.post('/upload-image', response_model=dict)
async def upload_bouquet_image(
    file: UploadFile = File(...),
    _: User = Depends(get_current_admin),
) -> dict[str, str]:
    content_type = (file.content_type or '').lower().strip()
    if content_type not in {'image/png', 'image/webp', 'image/jpeg', 'image/jpg'}:
        raise HTTPException(status_code=400, detail='Only PNG, WEBP and JPG are allowed')

    if content_type == 'image/png':
        ext = '.png'
    elif content_type in {'image/jpeg', 'image/jpg'}:
        ext = '.jpg'
    else:
        ext = '.webp'
    _ensure_images_dir()

    filename = f'{uuid.uuid4().hex}{ext}'
    target_path = BOUQUET_IMAGES_DIR / filename
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail='Empty file')
    target_path.write_bytes(body)

    return {'image_url': f'/api/v1/bouquets/images/{filename}'}


@router.get('/images/{name}')
async def get_bouquet_image(name: str) -> FileResponse:
    if '/' in name or '\\' in name:
        raise HTTPException(status_code=400, detail='Invalid image name')

    target_path = BOUQUET_IMAGES_DIR / name
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail='Image not found')

    suffix = target_path.suffix.lower()
    if suffix == '.webp':
        media_type = 'image/webp'
    elif suffix in {'.jpg', '.jpeg'}:
        media_type = 'image/jpeg'
    else:
        media_type = 'image/png'
    return FileResponse(path=str(target_path), media_type=media_type)


@router.get('/{bouquet_id}', response_model=Bouquet)
async def get_bouquet(bouquet_id: int, db: AsyncSession = Depends(get_db)) -> Bouquet:
    bouquet = await bouquet_crud.get(db, bouquet_id)
    if not bouquet:
        raise HTTPException(status_code=404, detail='Bouquet not found')
    return bouquet


@router.put('/{bouquet_id}', response_model=Bouquet)
async def update_bouquet(
    bouquet_id: int,
    bouquet_in: BouquetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> Bouquet:
    bouquet = await bouquet_crud.get(db, bouquet_id)
    if not bouquet:
        raise HTTPException(status_code=404, detail='Bouquet not found')
    _ = current_user
    return await bouquet_crud.update(db, bouquet, bouquet_in)


@router.delete('/{bouquet_id}', status_code=204)
async def delete_bouquet(
    bouquet_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> None:
    bouquet = await bouquet_crud.get(db, bouquet_id)
    if not bouquet:
        raise HTTPException(status_code=404, detail='Bouquet not found')
    _ = current_user
    await bouquet_crud.delete(db, bouquet)
