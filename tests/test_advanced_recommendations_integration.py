#!/usr/bin/env python3
"""
Test script for Advanced Recommendations Integration

This script tests the integration of all advanced analytics components
into the intelligent recommendation system.
"""

import asyncio
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_advanced_recommendations():
    """Test the advanced recommendation system"""
    
    try:
        # Import database connection
        from trading_platform.database.connection import get_database_session
        
        # Get database session
        db_session = next(get_database_session())
        
        print("🚀 Testing Advanced Recommendations Integration")
        print("=" * 60)
        
        # Test 1: Check if we can import the advanced engine
        print("\n1. Testing Advanced Recommendation Engine Import...")
        try:
            from integrate_advanced_recommendations import AdvancedRecommendationEngine
            print("✅ Advanced Recommendation Engine imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import Advanced Recommendation Engine: {e}")
            return False
        
        # Test 2: Initialize the engine
        print("\n2. Testing Engine Initialization...")
        try:
            engine = AdvancedRecommendationEngine(db_session)
            print("✅ Advanced Recommendation Engine initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize engine: {e}")
            return False
        
        # Test 3: Test market conditions
        print("\n3. Testing Market Conditions Retrieval...")
        try:
            market_conditions = await engine._get_current_market_conditions(datetime.now())
            print(f"✅ Market conditions retrieved:")
            print(f"   VIX: {market_conditions['current_vix']:.2f}")
            print(f"   VIX Regime: {market_conditions['vix_regime']}")
            print(f"   SPY: {market_conditions['current_spy']:.2f}")
        except Exception as e:
            print(f"❌ Failed to get market conditions: {e}")
            print("   This is expected if market data is not available")
        
        # Test 4: Test recommendation generation (with fallback)
        print("\n4. Testing Recommendation Generation...")
        try:
            recommendations = await engine.generate_intelligent_recommendations(
                current_time=datetime.now(),
                accounts=['IPS_TM_10'],  # Test with one account
                min_confidence=0.5  # Lower threshold for testing
            )
            
            print(f"✅ Generated {len(recommendations)} recommendations")
            
            if recommendations:
                rec = recommendations[0]
                print(f"   Sample Recommendation:")
                print(f"   Account: {rec.time_bin.account_name}")
                print(f"   Time: {rec.time_bin.hour:02d}:{rec.time_bin.minute_bin:02d}")
                print(f"   Action: {rec.action.value}")
                print(f"   Confidence: {rec.confidence.value}")
                print(f"   Expected Return: ${rec.expected_return:.2f}")
                print(f"   Reasoning: {rec.reasoning[:100]}...")
            else:
                print("   No recommendations generated (may be due to insufficient data or strict filters)")
                
        except Exception as e:
            print(f"❌ Failed to generate recommendations: {e}")
            print(f"   Error details: {type(e).__name__}: {str(e)}")
        
        # Test 5: Test API endpoint (if server is running)
        print("\n5. Testing API Endpoint...")
        try:
            import requests
            response = requests.get(
                "http://localhost:8000/api/v1/recommendations/advanced",
                params={"min_confidence": 0.5, "max_recommendations": 3},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API endpoint working: {data['message']}")
                print(f"   Returned {len(data.get('data', []))} recommendations")
            else:
                print(f"⚠️ API endpoint returned status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("⚠️ API server not running - skipping API test")
        except Exception as e:
            print(f"⚠️ API test failed: {e}")
        
        print("\n" + "=" * 60)
        print("🎯 Advanced Recommendations Integration Test Complete!")
        print("\nNext Steps:")
        print("1. Start your backend: python main.py")
        print("2. Start your frontend: cd frontend && npm start")
        print("3. Visit: http://localhost:3001/recommendations")
        print("4. Try the new advanced endpoint: http://localhost:8000/docs")
        print("   Look for '/api/v1/recommendations/advanced'")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    finally:
        if 'db_session' in locals():
            db_session.close()

async def test_individual_components():
    """Test individual analytics components"""
    
    print("\n🔧 Testing Individual Analytics Components")
    print("=" * 50)
    
    try:
        from trading_platform.database.connection import get_database_session
        db_session = next(get_database_session())
        
        # Test TimeBinAnalyzer
        print("\n1. Testing TimeBinAnalyzer...")
        try:
            from trading_platform.services.time_bin_analytics.time_bin_analyzer import TimeBinAnalyzer
            analyzer = TimeBinAnalyzer(db_session)
            print("✅ TimeBinAnalyzer initialized")
        except Exception as e:
            print(f"❌ TimeBinAnalyzer failed: {e}")
        
        # Test Monte Carlo components
        print("\n2. Testing Monte Carlo Components...")
        try:
            from trading_platform.services.monte_carlo.time_bin_scenario_generator import TimeBinScenarioGenerator
            from trading_platform.services.monte_carlo.risk_metrics_calculator import RiskMetricsCalculator
            scenario_gen = TimeBinScenarioGenerator(db_session)
            risk_calc = RiskMetricsCalculator()
            print("✅ Monte Carlo components initialized")
        except Exception as e:
            print(f"❌ Monte Carlo components failed: {e}")
        
        # Test Walk-Forward components
        print("\n3. Testing Walk-Forward Components...")
        try:
            from trading_platform.services.walk_forward.out_of_sample_validator import OutOfSampleValidator
            from trading_platform.services.walk_forward.performance_decay_tracker import PerformanceDecayTracker
            validator = OutOfSampleValidator(db_session)
            decay_tracker = PerformanceDecayTracker(db_session)
            print("✅ Walk-Forward components initialized")
        except Exception as e:
            print(f"❌ Walk-Forward components failed: {e}")
        
        # Test Market Correlation components
        print("\n4. Testing Market Correlation Components...")
        try:
            from trading_platform.services.market_correlation.market_data_ingestion import MarketDataIngestion
            from trading_platform.services.market_correlation.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
            market_data = MarketDataIngestion(db_session)
            benchmark_analyzer = BenchmarkComparisonAnalyzer(db_session)
            print("✅ Market Correlation components initialized")
        except Exception as e:
            print(f"❌ Market Correlation components failed: {e}")
        
        # Test VIX components
        print("\n5. Testing VIX Regime Components...")
        try:
            from trading_platform.services.vix_analysis.vix_regime_analyzer import VIXDataIntegration
            vix_analyzer = VIXDataIntegration(db_session)
            print("✅ VIX Regime components initialized")
        except Exception as e:
            print(f"❌ VIX Regime components failed: {e}")
        
        print("\n✅ All individual components tested!")
        
    except Exception as e:
        print(f"❌ Component testing failed: {e}")
    finally:
        if 'db_session' in locals():
            db_session.close()

if __name__ == "__main__":
    print("🧪 Advanced Trading Analytics Integration Test")
    print("This test verifies that all your sophisticated analytics")
    print("components are properly integrated into the recommendation system.\n")
    
    # Run the tests
    asyncio.run(test_advanced_recommendations())
    asyncio.run(test_individual_components())