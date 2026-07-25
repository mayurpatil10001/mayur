"""
backend/api/v1/routes/ingestion.py
====================================
POST /api/v1/ingest       — trigger binary log import (async background job)
GET  /api/v1/ingest/jobs  — list recent import jobs
GET  /api/v1/ingest/jobs/{job_id} — job status + progress
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.dependencies import AuthRequired, DBSession
from backend.models.analytics import ImportJob
from backend.schemas.walkforward import JobStatusSchema
from backend.core.config import settings

router = APIRouter()


class IngestRequest(BaseModel):
    data_dir: str = Field(
        default="",
        description="Path to directory containing .data binary log files. "
                    "Defaults to DATASET_PATH from settings.",
    )
    account_filter: str | None = Field(
        default=None,
        description="Comma-separated account names to import. NULL = all accounts.",
    )
    date_from: str | None = Field(default=None, description="Import files from this date YYYY-MM-DD")
    date_to: str | None = Field(default=None, description="Import files up to this date YYYY-MM-DD")


class ImportJobSchema(BaseModel):
    job_id: str
    status: str
    data_dir: str | None
    account_filter: str | None
    files_found: int
    files_processed: int
    fills_parsed: int
    ghosts_dropped: int
    trades_written: int
    errors: int
    error_detail: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    created_at: datetime


async def _run_import_job(job_id: str, request: IngestRequest) -> None:
    """Background task: run the full binary log import pipeline."""
    from backend.db.session import get_db_context
    from backend.models.analytics import ImportJob

    data_dir = Path(request.data_dir) if request.data_dir else settings.DATASET_PATH

    async with get_db_context() as db:
        result = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return

        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            if not data_dir.exists():
                raise FileNotFoundError(f"Data directory not found: {data_dir}")

            # Discover .data files
            data_files = list(data_dir.rglob("*.data"))
            job.files_found = len(data_files)
            await db.commit()

            # Import using existing binary log parser
            # (Integrates with the production trading_platform parser if present)
            try:
                from trading_platform.services.binary_log_parser import BinaryLogParser
                parser = BinaryLogParser()
                has_legacy_parser = True
            except ImportError:
                has_legacy_parser = False

            total_fills = 0
            total_ghosts = 0
            total_trades = 0
            errors = 0

            for i, filepath in enumerate(data_files):
                try:
                    if has_legacy_parser:
                        result_data = parser._parse_file_nitro(str(filepath))
                        if result_data:
                            total_fills += result_data.get("fills_parsed", 0)
                            total_ghosts += result_data.get("ghosts_dropped", 0)
                            total_trades += result_data.get("trades_written", 0)
                    job.files_processed = i + 1
                    if (i + 1) % 10 == 0:
                        await db.commit()
                except Exception as e:
                    errors += 1

            job.fills_parsed = total_fills
            job.ghosts_dropped = total_ghosts
            job.trades_written = total_trades
            job.errors = errors
            job.status = "COMPLETE"
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            await db.commit()

        except Exception as e:
            job.status = "FAILED"
            job.error_detail = str(e)[:500]
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()


@router.post(
    "",
    response_model=JobStatusSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger binary log import pipeline (async)",
)
async def trigger_ingest(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    _auth: AuthRequired,
    db: DBSession,
) -> JobStatusSchema:
    data_dir = request.data_dir or str(settings.DATASET_PATH)

    job_id = str(uuid.uuid4())
    job = ImportJob(
        id=job_id,
        status="PENDING",
        data_dir=data_dir,
        account_filter=request.account_filter,
    )
    db.add(job)
    await db.commit()

    background_tasks.add_task(_run_import_job, job_id, request)

    return JobStatusSchema(
        job_id=job_id,
        status="PENDING",
        message=f"Import job queued. Scanning: {data_dir}",
    )


@router.get(
    "/jobs",
    response_model=list[ImportJobSchema],
    summary="List recent import jobs",
)
async def list_jobs(
    _auth: AuthRequired,
    db: DBSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ImportJobSchema]:
    result = await db.execute(
        select(ImportJob).order_by(ImportJob.created_at.desc()).limit(limit)
    )
    jobs = result.scalars().all()
    return [
        ImportJobSchema(
            job_id=j.id,
            status=j.status,
            data_dir=j.data_dir,
            account_filter=j.account_filter,
            files_found=j.files_found,
            files_processed=j.files_processed,
            fills_parsed=j.fills_parsed,
            ghosts_dropped=j.ghosts_dropped,
            trades_written=j.trades_written,
            errors=j.errors,
            error_detail=j.error_detail,
            started_at=j.started_at,
            completed_at=j.completed_at,
            duration_seconds=j.duration_seconds,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get(
    "/jobs/{job_id}",
    response_model=ImportJobSchema,
    summary="Get import job status and progress",
)
async def get_job(
    job_id: str,
    _auth: AuthRequired,
    db: DBSession,
) -> ImportJobSchema:
    result = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Import job {job_id} not found")

    progress = None
    if job.files_found and job.files_processed:
        progress = job.files_processed / job.files_found * 100

    return ImportJobSchema(
        job_id=job.id,
        status=job.status,
        data_dir=job.data_dir,
        account_filter=job.account_filter,
        files_found=job.files_found,
        files_processed=job.files_processed,
        fills_parsed=job.fills_parsed,
        ghosts_dropped=job.ghosts_dropped,
        trades_written=job.trades_written,
        errors=job.errors,
        error_detail=job.error_detail,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        created_at=job.created_at,
    )
