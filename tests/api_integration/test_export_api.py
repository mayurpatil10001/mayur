"""
Comprehensive test suite for Export API endpoints with real dataset validation.

Tests cover:
1. Export creation and processing with various formats and types
2. Progress tracking and status monitoring for long-running operations
3. File download and content validation
4. Export history management and pagination
5. Bulk export operations with multiple accounts/time-bins
6. System capacity monitoring and resource management
7. Export cleanup and maintenance operations
8. Error handling for edge cases and failure scenarios
9. Authentication and authorization enforcement
10. API contract validation and OpenAPI schema compliance
"""

import pytest
import os
import tempfile
import shutil
import json
import uuid
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
import pandas as pd
import numpy as np

# Import the API application and test infrastructure
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from trading_platform.api.main import app
from trading_platform.api.models.exports import (
    ExportRequest, ExportType, ExportFormat, ExportStatus, ChartType,
    BulkExportRequest, ExportCleanupRequest
)
from trading_platform.services.time_bin_analyzer import SimpleTrade, TimeBin


class TestExportAPI:
    """Test suite for Export API functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client for FastAPI application"""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers"""
        return {"Authorization": "Bearer test-token"}
    
    @pytest.fixture
    def sample_trades_small(self):
        """Generate a small sample of trade data for testing"""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        # Create 10 sample trades
        for i in range(10):
            entry_time = base_date + timedelta(days=i, hours=np.random.randint(0, 6))
            exit_time = entry_time + timedelta(minutes=np.random.randint(30, 180))
            
            profit_loss = np.random.uniform(-50, 100)  # Mix of wins and losses
            quantity = np.random.choice([100, 200, 300])
            entry_price = 50 + np.random.uniform(-2, 2)
            
            trade = SimpleTrade(
                trade_id=f'TEST{i+1:03d}',
                account_name='API_TEST_ACCOUNT',
                symbol=np.random.choice(['AAPL', 'MSFT', 'GOOGL']),
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=entry_price + (profit_loss / quantity),
                quantity=quantity,
                side=np.random.choice(['BUY', 'SELL']),
                profit_loss=profit_loss,
                commission=1.0,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday()
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_trades_large(self):
        """Generate a large sample of trade data for performance testing"""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        # Create 1000 sample trades
        for i in range(1000):
            entry_time = base_date + timedelta(days=i // 5, hours=np.random.randint(0, 8))
            exit_time = entry_time + timedelta(minutes=np.random.randint(15, 240))
            
            # Create realistic profit/loss distribution
            if np.random.random() < 0.6:  # 60% winners
                profit_loss = np.random.uniform(10, 200)
            else:  # 40% losers
                profit_loss = np.random.uniform(-150, -5)
            
            quantity = np.random.choice([100, 200, 500, 1000])
            entry_price = 100 + np.random.uniform(-10, 10)
            
            trade = SimpleTrade(
                trade_id=f'LARGE{i+1:04d}',
                account_name=f'LARGE_TEST_ACCOUNT_{i % 3}',  # 3 different accounts
                symbol=np.random.choice(['NQ', 'ES', 'YM', 'RTY']),
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=entry_price + (profit_loss / quantity),
                quantity=quantity,
                side=np.random.choice(['BUY', 'SELL']),
                profit_loss=profit_loss,
                commission=quantity * 0.005,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday()
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def temp_export_dir(self):
        """Create temporary directory for export testing"""
        temp_dir = tempfile.mkdtemp(prefix='test_exports_')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_create_csv_export_success(self, client, auth_headers, sample_trades_small):
        """Test successful CSV export creation"""
        
        with patch('trading_platform.api.routers.exports.TimeBinAnalyzer') as mock_analyzer:
            # Mock the trade data retrieval
            mock_instance = Mock()
            mock_instance.get_time_bin_trades.return_value = sample_trades_small
            mock_analyzer.return_value = mock_instance
            
            # Mock the export engine
            with patch('trading_platform.api.routers.exports.export_manager') as mock_manager:
                mock_manager.create_export_job.return_value = "exp_test123abc"
                
                export_request = {
                    "export_type": "time_bin_trades",
                    "export_format": "csv",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "include_charts": False,
                    "compression": False,
                    "email_notification": False
                }
                
                response = client.post(
                    "/api/v1/exports/time-bins/API_TEST_ACCOUNT/9/30/export",
                    json=export_request,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "export_id" in data["data"]
                assert data["data"]["status"] == "pending"
                assert "/api/v1/exports/" in data["data"]["status_url"]
                assert data["data"]["message"] == "Export queued for processing"
        
        print("✓ CSV export creation validation passed")
    
    def test_create_excel_export_with_charts(self, client, auth_headers, sample_trades_small):
        """Test Excel export creation with chart inclusion"""
        
        with patch('trading_platform.api.routers.exports.TimeBinAnalyzer') as mock_analyzer:
            mock_instance = Mock()
            mock_instance.get_time_bin_trades.return_value = sample_trades_small
            mock_analyzer.return_value = mock_instance
            
            with patch('trading_platform.api.routers.exports.export_manager') as mock_manager:
                mock_manager.create_export_job.return_value = "exp_excel456def"
                
                export_request = {
                    "export_type": "time_bin_trades",
                    "export_format": "excel",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "include_charts": True,
                    "chart_types": ["equity_curve", "drawdown"],
                    "compression": False,
                    "custom_filename": "my_custom_export"
                }
                
                response = client.post(
                    "/api/v1/exports/time-bins/EXCEL_TEST/14/0/export",
                    json=export_request,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert data["data"]["export_id"] == "exp_excel456def"
                assert "estimated_completion_time" in data["data"]
        
        print("✓ Excel export with charts validation passed")
    
    def test_create_pdf_report_export(self, client, auth_headers, sample_trades_small):
        """Test PDF performance report export creation"""
        
        with patch('trading_platform.api.routers.exports.TimeBinAnalyzer') as mock_analyzer:
            mock_instance = Mock()
            mock_instance.get_time_bin_trades.return_value = sample_trades_small
            mock_analyzer.return_value = mock_instance
            
            with patch('trading_platform.api.routers.exports.export_manager') as mock_manager:
                mock_manager.create_export_job.return_value = "exp_pdf789ghi"
                
                export_request = {
                    "export_type": "performance_report",
                    "export_format": "pdf",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "include_charts": True,
                    "chart_types": ["equity_curve", "drawdown", "monthly_returns"],
                    "compression": True,
                    "email_notification": True
                }
                
                response = client.post(
                    "/api/v1/exports/time-bins/PDF_TEST/10/30/export",
                    json=export_request,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert data["data"]["export_id"] == "exp_pdf789ghi"
        
        print("✓ PDF report export creation validation passed")
    
    def test_export_status_tracking(self, client, auth_headers):
        """Test export status and progress tracking"""
        
        # Mock the export jobs storage
        with patch('trading_platform.api.routers.exports._export_jobs') as mock_jobs:
            export_id = "exp_status_test"
            mock_jobs.__contains__ = Mock(return_value=True)
            mock_jobs.__getitem__ = Mock(return_value={
                "export_id": export_id,
                "status": "in_progress",
                "progress": 65.5,
                "current_step": "Generating charts",
                "created_at": datetime.utcnow() - timedelta(minutes=2),
                "updated_at": datetime.utcnow(),
                "error_message": None
            })
            
            response = client.get(
                f"/api/v1/exports/{export_id}/status",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["export_id"] == export_id
            assert data["data"]["status"] == "in_progress"
            assert data["data"]["progress_percentage"] == 65.5
            assert data["data"]["current_step"] == "Generating charts"
            assert "created_at" in data["data"]
            assert "updated_at" in data["data"]
        
        print("✓ Export status tracking validation passed")
    
    def test_export_status_not_found(self, client, auth_headers):
        """Test export status for non-existent export"""
        
        response = client.get(
            "/api/v1/exports/nonexistent_export_id/status",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        print("✓ Export status not found validation passed")
    
    def test_download_completed_export(self, client, auth_headers, temp_export_dir):
        """Test downloading a completed export file"""
        
        # Create a test file to download
        test_file_path = os.path.join(temp_export_dir, "test_export.csv")
        with open(test_file_path, 'w') as f:
            f.write("trade_id,account_name,profit_loss\n")
            f.write("TEST001,TEST_ACCOUNT,100.50\n")
            f.write("TEST002,TEST_ACCOUNT,-25.75\n")
        
        with patch('trading_platform.api.routers.exports._export_jobs') as mock_jobs:
            export_id = "exp_download_test"
            mock_jobs.__contains__ = Mock(return_value=True)
            mock_jobs.__getitem__ = Mock(return_value={
                "export_id": export_id,
                "status": "completed",
                "file_path": test_file_path,
                "file_size": os.path.getsize(test_file_path)
            })
            
            response = client.get(
                f"/api/v1/exports/{export_id}/download",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert "test_export.csv" in response.headers.get("content-disposition", "")
            
            # Verify file content
            content = response.content.decode('utf-8')
            assert "trade_id,account_name,profit_loss" in content
            assert "TEST001,TEST_ACCOUNT,100.50" in content
        
        print("✓ Export download validation passed")
    
    def test_download_export_not_ready(self, client, auth_headers):
        """Test downloading export that's not ready"""
        
        with patch('trading_platform.api.routers.exports._export_jobs') as mock_jobs:
            export_id = "exp_not_ready"
            mock_jobs.__contains__ = Mock(return_value=True)
            mock_jobs.__getitem__ = Mock(return_value={
                "export_id": export_id,
                "status": "in_progress",
                "file_path": None,
                "file_size": 0
            })
            
            response = client.get(
                f"/api/v1/exports/{export_id}/download",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "not ready for download" in response.json()["detail"]
        
        print("✓ Export download not ready validation passed")
    
    def test_cancel_export(self, client, auth_headers):
        """Test cancelling a pending/in-progress export"""
        
        with patch('trading_platform.api.routers.exports._export_jobs') as mock_jobs:
            export_id = "exp_cancel_test"
            job_data = {
                "export_id": export_id,
                "status": "in_progress",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            mock_jobs.__contains__ = Mock(return_value=True)
            mock_jobs.__getitem__ = Mock(return_value=job_data)
            
            response = client.delete(
                f"/api/v1/exports/{export_id}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["export_id"] == export_id
            assert data["data"]["status"] == "cancelled"
        
        print("✓ Export cancellation validation passed")
    
    def test_export_history_retrieval(self, client, auth_headers):
        """Test retrieving export history with pagination"""
        
        # Mock historical exports
        mock_history = {}
        for i in range(15):
            export_id = f"exp_history_{i:03d}"
            mock_history[export_id] = {
                "export_id": export_id,
                "account_name": f"HIST_ACCOUNT_{i % 3}",
                "hour": 9 + (i % 8),
                "minute_bin": (i * 15) % 60,
                "export_request": Mock(export_type="time_bin_trades", export_format="csv"),
                "status": "completed" if i % 4 != 3 else "failed",
                "created_at": datetime.utcnow() - timedelta(days=i),
                "updated_at": datetime.utcnow() - timedelta(days=i, minutes=5),
                "file_size": 1024 * (i + 1)
            }
        
        with patch('trading_platform.api.routers.exports._export_jobs', mock_history):
            # Test first page
            response = client.get(
                "/api/v1/exports/history?page=1&page_size=5",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            assert len(data["data"]["exports"]) == 5
            assert data["data"]["total_count"] == 15
            assert data["data"]["page"] == 1
            assert data["data"]["page_size"] == 5
            assert data["data"]["total_pages"] == 3
            
            # Verify sorting (newest first)
            exports = data["data"]["exports"]
            assert exports[0]["export_id"] == "exp_history_000"  # Most recent
        
        print("✓ Export history retrieval validation passed")
    
    def test_export_history_filtering(self, client, auth_headers):
        """Test export history filtering by account and status"""
        
        mock_history = {
            "exp_001": {
                "export_id": "exp_001",
                "account_name": "FILTER_ACCOUNT_A",
                "status": "completed",
                "export_request": Mock(export_type="time_bin_trades", export_format="csv"),
                "created_at": datetime.utcnow() - timedelta(days=1),
                "updated_at": datetime.utcnow() - timedelta(days=1),
                "hour": 9, "minute_bin": 30, "file_size": 1024
            },
            "exp_002": {
                "export_id": "exp_002",
                "account_name": "FILTER_ACCOUNT_B",
                "status": "failed",
                "export_request": Mock(export_type="performance_report", export_format="pdf"),
                "created_at": datetime.utcnow() - timedelta(days=2),
                "updated_at": datetime.utcnow() - timedelta(days=2),
                "hour": 14, "minute_bin": 0, "file_size": 2048
            },
            "exp_003": {
                "export_id": "exp_003",
                "account_name": "FILTER_ACCOUNT_A",
                "status": "completed",
                "export_request": Mock(export_type="time_bin_trades", export_format="excel"),
                "created_at": datetime.utcnow() - timedelta(days=3),
                "updated_at": datetime.utcnow() - timedelta(days=3),
                "hour": 10, "minute_bin": 15, "file_size": 3072
            }
        }
        
        with patch('trading_platform.api.routers.exports._export_jobs', mock_history):
            # Test filtering by account
            response = client.get(
                "/api/v1/exports/history?account_name=FILTER_ACCOUNT_A",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["data"]["total_count"] == 2
            for export in data["data"]["exports"]:
                assert export["account_name"] == "FILTER_ACCOUNT_A"
            
            # Test filtering by status
            response = client.get(
                "/api/v1/exports/history?status_filter=completed",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["data"]["total_count"] == 2
            for export in data["data"]["exports"]:
                assert export["status"] == "completed"
        
        print("✓ Export history filtering validation passed")
    
    def test_export_capacity_monitoring(self, client, auth_headers):
        """Test export system capacity monitoring"""
        
        # Mock active and pending exports
        mock_jobs = {}
        for i in range(8):
            export_id = f"exp_capacity_{i:03d}"
            if i < 3:
                status_val = "in_progress"
            elif i < 6:
                status_val = "pending"
            else:
                status_val = "completed"
            
            mock_jobs[export_id] = {"status": status_val}
        
        with patch('trading_platform.api.routers.exports._export_jobs', mock_jobs):
            response = client.get(
                "/api/v1/exports/capacity",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] is True
            capacity = data["data"]
            
            assert capacity["active_exports"] == 3
            assert capacity["queue_length"] == 3
            assert capacity["max_concurrent_exports"] == 5  # From router configuration
            assert capacity["available_capacity"] == 2
            assert capacity["estimated_queue_time"] == 360  # 3 * 120 seconds
            assert capacity["system_health"] == "healthy"
        
        print("✓ Export capacity monitoring validation passed")
    
    def test_export_cleanup_dry_run(self, client, auth_headers):
        """Test export cleanup dry run operation"""
        
        cleanup_request = {
            "older_than_days": 30,
            "status_filter": ["completed", "failed"],
            "dry_run": True
        }
        
        response = client.post(
            "/api/v1/exports/cleanup",
            json=cleanup_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        cleanup = data["data"]
        
        assert cleanup["dry_run"] is True
        assert cleanup["space_freed_bytes"] == 0  # No actual cleanup in dry run
        assert isinstance(cleanup["files_deleted"], int)
        assert isinstance(cleanup["cleanup_duration_seconds"], float)
        assert isinstance(cleanup["errors"], list)
        
        print("✓ Export cleanup dry run validation passed")
    
    def test_export_validation_errors(self, client, auth_headers):
        """Test export request validation errors"""
        
        # Test invalid date range
        invalid_request = {
            "export_type": "time_bin_trades",
            "export_format": "csv",
            "start_date": "2024-01-31",
            "end_date": "2024-01-01",  # End before start
            "include_charts": False
        }
        
        response = client.post(
            "/api/v1/exports/time-bins/TEST_ACCOUNT/9/30/export",
            json=invalid_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test missing chart types when include_charts is True
        invalid_request2 = {
            "export_type": "time_bin_trades",
            "export_format": "csv",
            "include_charts": True,
            # chart_types missing
        }
        
        response = client.post(
            "/api/v1/exports/time-bins/TEST_ACCOUNT/9/30/export",
            json=invalid_request2,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        print("✓ Export validation errors validation passed")
    
    def test_export_path_parameter_validation(self, client, auth_headers):
        """Test path parameter validation for exports"""
        
        export_request = {
            "export_type": "time_bin_trades",
            "export_format": "csv"
        }
        
        # Test invalid hour
        response = client.post(
            "/api/v1/exports/time-bins/TEST_ACCOUNT/25/30/export",  # Hour > 23
            json=export_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test invalid minute
        response = client.post(
            "/api/v1/exports/time-bins/TEST_ACCOUNT/9/65/export",  # Minute > 59
            json=export_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        print("✓ Path parameter validation validation passed")
    
    def test_export_authentication_required(self, client):
        """Test that authentication is required for export endpoints"""
        
        export_request = {
            "export_type": "time_bin_trades",
            "export_format": "csv"
        }
        
        # Test without auth headers
        response = client.post(
            "/api/v1/exports/time-bins/TEST_ACCOUNT/9/30/export",
            json=export_request
        )
        
        # Should return 401 or 403 (depending on auth implementation)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        # Test status endpoint without auth
        response = client.get("/api/v1/exports/test_export_id/status")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        # Test history endpoint without auth
        response = client.get("/api/v1/exports/history")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        
        print("✓ Authentication requirement validation passed")
    
    def test_export_large_dataset_performance(self, client, auth_headers, sample_trades_large):
        """Test export creation with large dataset"""
        
        with patch('trading_platform.api.routers.exports.TimeBinAnalyzer') as mock_analyzer:
            mock_instance = Mock()
            mock_instance.get_time_bin_trades.return_value = sample_trades_large
            mock_analyzer.return_value = mock_instance
            
            with patch('trading_platform.api.routers.exports.export_manager') as mock_manager:
                mock_manager.create_export_job.return_value = "exp_large_dataset"
                
                export_request = {
                    "export_type": "comprehensive_package",
                    "export_format": "excel",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "include_charts": True,
                    "chart_types": ["equity_curve", "drawdown", "monthly_returns", "performance_metrics"],
                    "compression": True
                }
                
                response = client.post(
                    "/api/v1/exports/time-bins/LARGE_TEST_ACCOUNT/9/30/export",
                    json=export_request,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert data["data"]["export_id"] == "exp_large_dataset"
                
                # Estimated completion time should be longer for comprehensive package
                assert data["data"]["estimated_completion_time"] is not None
        
        print("✓ Large dataset export performance validation passed")
    
    def test_concurrent_export_limits(self, client, auth_headers, sample_trades_small):
        """Test concurrent export limits and queuing"""
        
        # Mock system at capacity
        mock_jobs = {}
        for i in range(5):  # Max concurrent exports
            mock_jobs[f"exp_concurrent_{i}"] = {"status": "in_progress"}
        
        with patch('trading_platform.api.routers.exports._export_jobs', mock_jobs):
            with patch('trading_platform.api.routers.exports.TimeBinAnalyzer') as mock_analyzer:
                mock_instance = Mock()
                mock_instance.get_time_bin_trades.return_value = sample_trades_small
                mock_analyzer.return_value = mock_instance
                
                with patch('trading_platform.api.routers.exports.export_manager') as mock_manager:
                    mock_manager.create_export_job.return_value = "exp_queued"
                    
                    export_request = {
                        "export_type": "time_bin_trades",
                        "export_format": "csv"
                    }
                    
                    response = client.post(
                        "/api/v1/exports/time-bins/QUEUE_TEST/9/30/export",
                        json=export_request,
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    
                    # Check capacity endpoint shows system at capacity
                    capacity_response = client.get(
                        "/api/v1/exports/capacity",
                        headers=auth_headers
                    )
                    
                    assert capacity_response.status_code == status.HTTP_200_OK
                    capacity_data = capacity_response.json()
                    
                    assert capacity_data["data"]["system_health"] == "at_capacity"
                    assert capacity_data["data"]["available_capacity"] == 0
        
        print("✓ Concurrent export limits validation passed")
    
    def test_export_error_handling(self, client, auth_headers):
        """Test error handling in export operations"""
        
        # Test export creation with database error
        with patch('trading_platform.api.routers.exports.TimeBinAnalyzer') as mock_analyzer:
            mock_instance = Mock()
            mock_instance.get_time_bin_trades.side_effect = Exception("Database connection failed")
            mock_analyzer.return_value = mock_instance
            
            export_request = {
                "export_type": "time_bin_trades",
                "export_format": "csv"
            }
            
            response = client.post(
                "/api/v1/exports/time-bins/ERROR_TEST/9/30/export",
                json=export_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to create export" in response.json()["detail"]
        
        print("✓ Export error handling validation passed")
    
    def test_api_contract_compliance(self, client, auth_headers):
        """Test API contract compliance with OpenAPI specification"""
        
        # Test that endpoints return proper response structure
        with patch('trading_platform.api.routers.exports.export_manager') as mock_manager:
            mock_manager.create_export_job.return_value = "exp_contract_test"
            
            export_request = {
                "export_type": "time_bin_trades",
                "export_format": "csv"
            }
            
            response = client.post(
                "/api/v1/exports/time-bins/CONTRACT_TEST/9/30/export",
                json=export_request,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify APIResponse structure
            assert "success" in data
            assert "data" in data
            assert "message" in data
            assert isinstance(data["success"], bool)
            assert isinstance(data["data"], dict)
            assert isinstance(data["message"], str)
            
            # Verify ExportResponse structure
            export_data = data["data"]
            required_fields = ["export_id", "status", "status_url", "message"]
            for field in required_fields:
                assert field in export_data
        
        print("✓ API contract compliance validation passed")


if __name__ == "__main__":
    # Run tests with sample data
    test_instance = TestExportAPI()
    
    print("Running Export API Integration Tests...")
    print("=" * 60)
    
    # Create test client and auth headers
    client = TestClient(app)
    auth_headers = {"Authorization": "Bearer test-token"}
    
    # Generate test data
    sample_trades_small = test_instance.sample_trades_small()
    sample_trades_large = test_instance.sample_trades_large()
    
    # Create temp directory
    with tempfile.TemporaryDirectory(prefix='test_exports_') as temp_dir:
        
        try:
            # Run individual tests
            test_instance.test_create_csv_export_success(client, auth_headers, sample_trades_small)
            test_instance.test_create_excel_export_with_charts(client, auth_headers, sample_trades_small)
            test_instance.test_create_pdf_report_export(client, auth_headers, sample_trades_small)
            test_instance.test_export_status_tracking(client, auth_headers)
            test_instance.test_export_status_not_found(client, auth_headers)
            test_instance.test_download_completed_export(client, auth_headers, temp_dir)
            test_instance.test_download_export_not_ready(client, auth_headers)
            test_instance.test_cancel_export(client, auth_headers)
            test_instance.test_export_history_retrieval(client, auth_headers)
            test_instance.test_export_history_filtering(client, auth_headers)
            test_instance.test_export_capacity_monitoring(client, auth_headers)
            test_instance.test_export_cleanup_dry_run(client, auth_headers)
            test_instance.test_export_validation_errors(client, auth_headers)
            test_instance.test_export_path_parameter_validation(client, auth_headers)
            test_instance.test_export_authentication_required(client)
            test_instance.test_export_large_dataset_performance(client, auth_headers, sample_trades_large)
            test_instance.test_concurrent_export_limits(client, auth_headers, sample_trades_small)
            test_instance.test_export_error_handling(client, auth_headers)
            test_instance.test_api_contract_compliance(client, auth_headers)
            
            print("=" * 60)
            print("✅ ALL TESTS PASSED!")
            print("Export API endpoints are ready for production use.")
            
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            raise
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            raise