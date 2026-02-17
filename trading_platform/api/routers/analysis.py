from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
from datetime import datetime

from ..dependencies import get_database_session

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/jobs")
async def get_analysis_jobs(db: Session = Depends(get_database_session)) -> List[Dict[str, Any]]:
    """Get current and recent analysis jobs."""
    
    # For now, return empty list since we don't have a jobs table
    # In the future, you can track long-running queries or batch processes
    jobs = []
    
    # Check if there are any active database queries
    try:
        # PostgreSQL specific query to check active queries
        result = db.execute(text("""
            SELECT 
                pid,
                usename,
                application_name,
                state,
                query,
                state_change
            FROM pg_stat_activity 
            WHERE state = 'active' 
            AND query NOT LIKE '%pg_stat_activity%'
            AND pid != pg_backend_pid()
            LIMIT 10
        """))
        
        for row in result:
            # Extract query type
            query = row.query[:100] if row.query else "Unknown"
            
            jobs.append({
                "id": str(row.pid),
                "name": f"Query: {query}...",
                "status": "running",
                "progress": 50,  # Can't determine actual progress
                "startTime": row.state_change.isoformat() if row.state_change else datetime.now().isoformat(),
                "duration": None
            })
    except Exception as e:
        # If PostgreSQL specific query fails, return empty list
        pass
    
    return jobs


@router.get("/stats")
async def get_analysis_stats(db: Session = Depends(get_database_session)) -> Dict[str, Any]:
    """Get overall analysis statistics."""
    
    try:
        # Get total trades count
        trades_result = db.execute(text("SELECT COUNT(*) as count FROM processed_trades"))
        total_trades = trades_result.scalar()
        
        # Get total accounts
        accounts_result = db.execute(text("SELECT COUNT(DISTINCT account_name) as count FROM processed_trades"))
        total_accounts = accounts_result.scalar()
        
        # Get date range
        date_range_result = db.execute(text("""
            SELECT 
                MIN(entry_time) as first_trade,
                MAX(entry_time) as last_trade
            FROM processed_trades
        """))
        date_range = date_range_result.fetchone()
        
        return {
            "totalTrades": total_trades,
            "totalAccounts": total_accounts,
            "firstTrade": date_range.first_trade.isoformat() if date_range.first_trade else None,
            "lastTrade": date_range.last_trade.isoformat() if date_range.last_trade else None,
            "databaseSize": "N/A"  # Would need additional query
        }
    except Exception as e:
        return {
            "totalTrades": 0,
            "totalAccounts": 0,
            "firstTrade": None,
            "lastTrade": None,
            "error": str(e)
        }
