"""
Trade Import API endpoints.

Provides paste-based trade import with preview and commit workflows.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel, Field

from ..dependencies import require_write_permission
from ...services.trade_import_service import TradeImportService


router = APIRouter()


# ── Request / Response models ───────────────────────────────

class PasteImportRequest(BaseModel):
    """Request body for paste-based trade import."""
    text: str = Field(..., description="Tab-delimited trade data (copied from Sierra Chart)")


class ParsedTradeResponse(BaseModel):
    """Single parsed trade for preview."""
    account_name: str
    symbol: str
    base_symbol: str
    trade_type: str
    entry_datetime: str
    exit_datetime: str
    entry_price: float
    exit_price: float
    quantity: int
    profit_loss: float
    commission: float
    duration: str
    note: str


class ImportResultResponse(BaseModel):
    """Result of an import or preview operation."""
    total_parsed: int
    new_trades: int = 0
    duplicates: int = 0
    errors: list[str] = []
    trades: list[ParsedTradeResponse] = []
    rejected_trades: list[dict] = []
    dropped_ghost_fills: list[dict] = []
    stats: dict = {}


# ── Endpoints ───────────────────────────────────────────────

@router.post(
    "/import-preview",
    response_model=ImportResultResponse,
    summary="Preview pasted trades",
    description="Parse pasted Sierra Chart trade data and return a preview without inserting into the database.",
)
async def import_preview(
    request: PasteImportRequest = Body(...),
    current_user: dict = Depends(require_write_permission),
):
    """Dry-run: parse and return parsed trades without DB writes."""
    service = TradeImportService()
    result = service.preview(request.text)

    return ImportResultResponse(
        total_parsed=result.total_parsed,
        errors=result.errors,
        trades=[
            ParsedTradeResponse(
                account_name=t.account_name,
                symbol=t.symbol,
                base_symbol=t.base_symbol,
                trade_type=t.trade_type,
                entry_datetime=t.entry_datetime.isoformat(),
                exit_datetime=t.exit_datetime.isoformat(),
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                quantity=t.quantity,
                profit_loss=t.profit_loss,
                commission=t.commission,
                duration=t.duration,
                note=t.note,
            )
            for t in result.parsed_trades
        ],
        rejected_trades=result.rejected_trades,
        dropped_ghost_fills=result.dropped_ghost_fills,
    )


@router.post(
    "/import-paste",
    response_model=ImportResultResponse,
    summary="Import pasted trades",
    description="Parse pasted Sierra Chart trade data, deduplicate, and insert new trades into the database.",
)
async def import_paste(
    request: PasteImportRequest = Body(...),
    current_user: dict = Depends(require_write_permission),
):
    """Parse, deduplicate, and insert trades."""
    service = TradeImportService()
    result = service.import_trades(request.text)

    return ImportResultResponse(
        total_parsed=result.total_parsed,
        new_trades=result.new_trades,
        duplicates=result.duplicates,
        errors=result.errors,
        stats=result.stats,
        trades=[
            ParsedTradeResponse(
                account_name=t.account_name,
                symbol=t.symbol,
                base_symbol=t.base_symbol,
                trade_type=t.trade_type,
                entry_datetime=t.entry_datetime.isoformat(),
                exit_datetime=t.exit_datetime.isoformat(),
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                quantity=t.quantity,
                profit_loss=t.profit_loss,
                commission=t.commission,
                duration=t.duration,
                note=t.note,
            )
            for t in result.parsed_trades
        ],
        rejected_trades=result.rejected_trades,
        dropped_ghost_fills=result.dropped_ghost_fills,
    )
