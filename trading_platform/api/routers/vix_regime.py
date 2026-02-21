
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

from ..dependencies import get_database_session, require_read_permission
from ..models.common import APIResponse
from ...services.vix_regime_analyzer import VIXDataIntegration, VolatilityRegime

router = APIRouter()

def get_vix_analyzer(db: Session = Depends(get_database_session)) -> VIXDataIntegration:
    return VIXDataIntegration(db_session=db)

def parse_date(date_str: Optional[str], default: datetime) -> datetime:
    if not date_str:
        return default
    try:
        # Try ISO format first (handles T00:00:00)
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', ''))
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            return pd.to_datetime(date_str).to_pydatetime()
        except:
            return default

@router.get("/data")
async def get_vix_data(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=90))
        e_date = parse_date(end_date, datetime.now())
        
        vix_series = vix_analyzer.fetch_vix_data(s_date, e_date)
        classifications = vix_analyzer.classify_volatility_regimes(vix_series)
        
        # Return in the format expected by the frontend
        return [
            {
                "date": c.date.strftime("%Y-%m-%d"),
                "vix_level": c.vix_level,
                "regime": c.regime.value.upper(),
                "regime_duration_days": c.regime_duration_days
            }
            for c in classifications
        ]
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/{account_name}")
async def get_regime_performance(
    account_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=90))
        e_date = parse_date(end_date, datetime.now())
        
        alignments = vix_analyzer.synchronize_vix_with_trades(account_name, s_date, e_date)
        performance = vix_analyzer.analyze_regime_performance(alignments)
        
        # Format for frontend
        result = []
        for regime, metrics in performance.items():
            result.append({
                "account": account_name,
                "regime": regime.value.upper(),
                "performance_metrics": {
                    "total_pnl": metrics["total_pnl"],
                    "average_pnl": metrics["avg_pnl"],
                    "win_rate": metrics["win_rate"],
                    "profit_factor": metrics["profit_factor"],
                    "sharpe_ratio": metrics["sharpe_ratio"] or 0,
                    "total_trades": metrics["total_trades"]
                },
                "statistical_significance": {
                    "is_significant": True, # Placeholder
                    "p_value": 0.05
                }
            })
        return result
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transitions/{account_name}")
async def get_regime_transitions(
    account_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=90))
        e_date = parse_date(end_date, datetime.now())
        
        vix_series = vix_analyzer.fetch_vix_data(s_date, e_date)
        classifications = vix_analyzer.classify_volatility_regimes(vix_series)
        transitions = vix_analyzer.detect_regime_transitions(classifications)
        
        return [
            {
                "date": t.transition_date.strftime("%Y-%m-%d"),
                "from_regime": t.from_regime.value.upper(),
                "to_regime": t.to_regime.value.upper(),
                "trigger_vix_level": t.trigger_vix_level,
                "days_in_previous_regime": t.days_in_previous_regime,
                "performance_impact": {
                    "performance_change": 0 # Placeholder
                }
            }
            for t in transitions
        ]
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/current")
async def get_current_regime(
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    try:
        # Get last 252 trading days (~1 year) for historical transition analysis
        e_date = datetime.now()
        s_date = e_date - timedelta(days=365)
        
        vix_series = vix_analyzer.fetch_vix_data(s_date, e_date)
        classifications = vix_analyzer.classify_volatility_regimes(vix_series)
        
        if not classifications:
            raise HTTPException(status_code=404, detail="No VIX data found")
            
        current = classifications[-1]
        
        # Calculate percentile from historical data
        all_vix = [c.vix_level for c in classifications]
        below = sum(1 for v in all_vix if v < current.vix_level)
        percentile = (below / len(all_vix)) * 100 if all_vix else 50
        
        # Calculate regime forecast from historical transition probabilities
        # Find all transitions FROM the current regime type
        transitions = vix_analyzer.detect_regime_transitions(classifications)
        current_regime_val = current.regime.value.upper()
        from_current = [t for t in transitions if t.from_regime.value.upper() == current_regime_val]
        
        # Count where each transition goes
        transition_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for t in from_current:
            transition_counts[t.to_regime.value.upper()] += 1
        
        total_transitions = sum(transition_counts.values())
        if total_transitions > 0:
            # Probability of transitioning to each regime
            p_low = transition_counts["LOW"] / total_transitions
            p_med = transition_counts["MEDIUM"] / total_transitions
            p_high = transition_counts["HIGH"] / total_transitions
            # Also factor in probability of STAYING in current regime
            # (based on avg duration vs current duration)
            avg_duration = sum(t.days_in_previous_regime for t in from_current) / len(from_current)
            stay_prob = min(0.8, current.regime_duration_days / (avg_duration + 1))
            stay_prob = max(0, 1 - stay_prob)  # Higher duration = lower stay probability
            
            transition_probs = {
                "LOW": p_low * (1 - stay_prob),
                "MEDIUM": p_med * (1 - stay_prob),
                "HIGH": p_high * (1 - stay_prob)
            }
            transition_probs[current_regime_val] += stay_prob
        else:
            # No historical transitions, use regime frequency
            regime_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
            for c in classifications:
                regime_counts[c.regime.value.upper()] += 1
            total = len(classifications) or 1
            transition_probs = {k: v / total for k, v in regime_counts.items()}
        
        return {
            "current_vix_level": current.vix_level,
            "current_regime": current_regime_val,
            "days_in_current_regime": current.regime_duration_days,
            "regime_percentile": round(percentile, 1),
            "regime_forecast": {
                "probability_low": round(transition_probs["LOW"], 3),
                "probability_medium": round(transition_probs["MEDIUM"], 3),
                "probability_high": round(transition_probs["HIGH"], 3)
            }
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/distribution")
async def get_vix_distribution(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> List[Dict]:
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=90))
        e_date = parse_date(end_date, datetime.now())
        
        vix_series = vix_analyzer.fetch_vix_data(s_date, e_date)
        vix_levels = [float(val) for val in vix_series.data['Close'].values]
        
        # Calculate regime breakdown
        low_vals = [v for v in vix_levels if v < 15]
        med_vals = [v for v in vix_levels if 15 <= v <= 25]
        high_vals = [v for v in vix_levels if v > 25]
        
        total = len(vix_levels) or 1
        import statistics
        
        return [{
            "time_bin": "All Time",
            "vix_levels": vix_levels,
            "regime_counts": {
                "LOW": len(low_vals),
                "MEDIUM": len(med_vals),
                "HIGH": len(high_vals)
            },
            "regime_percentages": {
                "LOW": (len(low_vals) / total) * 100,
                "MEDIUM": (len(med_vals) / total) * 100,
                "HIGH": (len(high_vals) / total) * 100
            },
            "average_vix_by_regime": {
                "LOW": statistics.mean(low_vals) if low_vals else 0,
                "MEDIUM": statistics.mean(med_vals) if med_vals else 0,
                "HIGH": statistics.mean(high_vals) if high_vals else 0
            },
            "vix_statistics": {
                "min": min(vix_levels) if vix_levels else 0,
                "max": max(vix_levels) if vix_levels else 0,
                "mean": statistics.mean(vix_levels) if vix_levels else 0,
                "std": statistics.stdev(vix_levels) if len(vix_levels) > 1 else 0
            }
        }]
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pnl-correlation/{account_name}")
async def get_pnl_correlation(
    account_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    """VIX vs P&L correlation with scatter data, regression, and optimal range."""
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=365))
        e_date = parse_date(end_date, datetime.now())
        result = vix_analyzer.calculate_vix_pnl_correlation(account_name, s_date, e_date)
        return result
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/equity-by-regime/{account_name}")
async def get_equity_by_regime(
    account_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    """Cumulative equity curve annotated with VIX regime coloring."""
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=365))
        e_date = parse_date(end_date, datetime.now())
        result = vix_analyzer.get_equity_curve_with_regimes(account_name, s_date, e_date)
        return result
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timebin-heatmap/{account_name}")
async def get_timebin_heatmap(
    account_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
):
    """Time-bin × VIX regime cross-analysis for heatmap."""
    try:
        s_date = parse_date(start_date, datetime.now() - timedelta(days=365))
        e_date = parse_date(end_date, datetime.now())
        result = vix_analyzer.cross_analyze_timebins_by_regime(account_name, s_date, e_date)
        return result
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
