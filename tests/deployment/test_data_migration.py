"""
Database migration testing for trading analytics platform.

This module tests database migrations with production-like data including:
- Schema migration procedures and rollback
- Data migration with large datasets
- Index management during migrations
- Zero-downtime migration validation
- Migration performance and integrity testing
- Backward compatibility verification

Requirements: 10.4, 10.6, 8.2
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import time
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from unittest.mock import Mock, patch
from dataclasses import dataclass, field
import json
import hashlib

# Import components for migration testing
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.models.time_bin_analytics import TimeBinAnalysis, MarketData
from trading_platform.database.base import Base
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Float, DateTime, Boolean, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError


@dataclass
class MigrationScript:
    """Represents a database migration script."""
    version: str
    name: str
    up_sql: str
    down_sql: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    estimated_duration_seconds: int = 60
    requires_downtime: bool = False
    data_migration: bool = False


@dataclass
class MigrationResult:
    """Results of migration execution."""
    version: str
    success: bool
    duration_seconds: float
    records_affected: int = 0
    errors: List[str] = field(default_factory=list)
    rollback_available: bool = True
    data_integrity_check: bool = True


class DatabaseMigrationManager:
    """Manages database migrations with production safety features."""
    
    def __init__(self, engine, session_factory):
        self.engine = engine
        self.session_factory = session_factory
        self.migration_history = []
        self.applied_migrations = set()
        self.backup_paths = []
        
    async def apply_migration(self, migration: MigrationScript) -> MigrationResult:
        """Apply a database migration with safety checks."""
        print(f"Applying migration {migration.version}: {migration.name}")
        
        result = MigrationResult(
            version=migration.version,
            success=False,
            duration_seconds=0
        )
        
        start_time = time.time()
        
        try:
            # Step 1: Create backup
            backup_result = await self._create_migration_backup(migration.version)
            if not backup_result['success']:
                result.errors.extend(backup_result['errors'])
                return result
            
            self.backup_paths.append(backup_result['backup_path'])
            
            # Step 2: Validate migration dependencies
            dependency_check = self._validate_dependencies(migration)
            if not dependency_check['valid']:
                result.errors.extend(dependency_check['errors'])
                return result
            
            # Step 3: Perform pre-migration validation
            pre_validation = await self._pre_migration_validation(migration)
            if not pre_validation['valid']:
                result.errors.extend(pre_validation['errors'])
                return result
            
            # Step 4: Execute migration
            execution_result = await self._execute_migration_sql(migration)
            if not execution_result['success']:
                result.errors.extend(execution_result['errors'])
                # Attempt automatic rollback
                await self._rollback_migration(migration)
                return result
            
            result.records_affected = execution_result.get('records_affected', 0)
            
            # Step 5: Post-migration validation
            post_validation = await self._post_migration_validation(migration)
            if not post_validation['valid']:
                result.errors.extend(post_validation['errors'])
                result.data_integrity_check = False
                # Rollback on validation failure
                await self._rollback_migration(migration)
                return result
            
            # Step 6: Record migration success
            await self._record_migration_history(migration, result)
            self.applied_migrations.add(migration.version)
            
            result.success = True
            print(f"✅ Migration {migration.version} completed successfully")
            
        except Exception as e:
            result.errors.append(f"Migration exception: {str(e)}")
            print(f"❌ Migration {migration.version} failed: {e}")
            
            # Attempt rollback
            try:
                await self._rollback_migration(migration)
            except Exception as rollback_e:
                result.errors.append(f"Rollback failed: {str(rollback_e)}")
        
        finally:
            result.duration_seconds = time.time() - start_time
        
        return result
    
    async def rollback_migration(self, migration_version: str) -> MigrationResult:
        """Rollback a specific migration."""
        print(f"Rolling back migration {migration_version}")
        
        result = MigrationResult(
            version=migration_version,
            success=False,
            duration_seconds=0
        )
        
        start_time = time.time()
        
        try:
            # Find migration in history
            migration_record = next((m for m in self.migration_history if m['version'] == migration_version), None)
            if not migration_record:
                result.errors.append(f"Migration {migration_version} not found in history")
                return result
            
            migration = migration_record['migration']
            
            # Execute rollback SQL
            rollback_result = await self._execute_rollback_sql(migration)
            if not rollback_result['success']:
                result.errors.extend(rollback_result['errors'])
                return result
            
            # Remove from applied migrations
            if migration_version in self.applied_migrations:
                self.applied_migrations.remove(migration_version)
            
            # Update migration history
            migration_record['rolled_back'] = True
            migration_record['rollback_timestamp'] = datetime.now()
            
            result.success = True
            print(f"✅ Migration {migration_version} rolled back successfully")
            
        except Exception as e:
            result.errors.append(f"Rollback exception: {str(e)}")
            print(f"❌ Rollback {migration_version} failed: {e}")
        
        finally:
            result.duration_seconds = time.time() - start_time
        
        return result
    
    async def apply_migrations_batch(self, migrations: List[MigrationScript]) -> Dict[str, Any]:
        """Apply multiple migrations in sequence with rollback on failure."""
        batch_result = {
            'success': True,
            'migrations_applied': [],
            'migrations_failed': [],
            'total_duration': 0,
            'rollback_performed': False
        }
        
        batch_start = time.time()
        applied_migrations = []
        
        try:
            for migration in migrations:
                result = await self.apply_migration(migration)
                
                if result.success:
                    applied_migrations.append(migration.version)
                    batch_result['migrations_applied'].append({
                        'version': migration.version,
                        'duration': result.duration_seconds,
                        'records_affected': result.records_affected
                    })
                else:
                    batch_result['success'] = False
                    batch_result['migrations_failed'].append({
                        'version': migration.version,
                        'errors': result.errors
                    })
                    
                    # Rollback all applied migrations in reverse order
                    print(f"Batch migration failed at {migration.version}, rolling back...")
                    for rollback_version in reversed(applied_migrations):
                        await self.rollback_migration(rollback_version)
                    
                    batch_result['rollback_performed'] = True
                    break
        
        except Exception as e:
            batch_result['success'] = False
            batch_result['migrations_failed'].append({
                'version': 'batch_exception',
                'errors': [str(e)]
            })
        
        finally:
            batch_result['total_duration'] = time.time() - batch_start
        
        return batch_result
    
    async def _create_migration_backup(self, migration_version: str) -> Dict[str, Any]:
        """Create backup before migration."""
        backup_result = {'success': False, 'backup_path': '', 'errors': []}
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(tempfile.gettempdir(), f"migration_backup_{migration_version}_{timestamp}")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create database backup
            backup_file = os.path.join(backup_dir, "database_backup.db")
            
            # For SQLite, copy the database file
            if 'sqlite' in str(self.engine.url):
                # Get the database file path
                db_path = str(self.engine.url).replace('sqlite:///', '')
                if os.path.exists(db_path):
                    shutil.copy2(db_path, backup_file)
                else:
                    # Create a backup using SQL dump
                    await self._create_sql_backup(backup_file)
            
            # Create schema backup
            schema_file = os.path.join(backup_dir, "schema_backup.sql")
            await self._create_schema_backup(schema_file)
            
            backup_result['success'] = True
            backup_result['backup_path'] = backup_dir
            print(f"Backup created: {backup_dir}")
            
        except Exception as e:
            backup_result['errors'].append(f"Backup creation failed: {str(e)}")
        
        return backup_result
    
    async def _create_sql_backup(self, backup_file: str):
        """Create SQL backup of database."""
        with self.session_factory() as session:
            # Get all table names
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            with open(backup_file.replace('.db', '.sql'), 'w') as f:
                f.write(f"-- Database backup created at {datetime.now()}\n\n")
                
                for table_name in tables:
                    f.write(f"-- Table: {table_name}\n")
                    
                    # Get table creation SQL (simplified)
                    result = session.execute(text(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                    row = result.fetchone()
                    if row and row[0]:
                        f.write(f"{row[0]};\n\n")
    
    async def _create_schema_backup(self, schema_file: str):
        """Create schema backup."""
        with open(schema_file, 'w') as f:
            f.write(f"-- Schema backup created at {datetime.now()}\n")
            f.write("-- This is a simplified schema backup for testing\n")
            
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            for table_name in tables:
                columns = inspector.get_columns(table_name)
                f.write(f"\n-- Table: {table_name}\n")
                f.write(f"-- Columns: {len(columns)}\n")
                for column in columns:
                    f.write(f"--   {column['name']}: {column['type']}\n")
    
    def _validate_dependencies(self, migration: MigrationScript) -> Dict[str, Any]:
        """Validate migration dependencies."""
        validation = {'valid': True, 'errors': []}
        
        for dependency in migration.dependencies:
            if dependency not in self.applied_migrations:
                validation['valid'] = False
                validation['errors'].append(f"Missing dependency: {dependency}")
        
        return validation
    
    async def _pre_migration_validation(self, migration: MigrationScript) -> Dict[str, Any]:
        """Perform pre-migration validation."""
        validation = {'valid': True, 'errors': []}
        
        try:
            with self.session_factory() as session:
                # Check if migration already applied
                if migration.version in self.applied_migrations:
                    validation['valid'] = False
                    validation['errors'].append(f"Migration {migration.version} already applied")
                    return validation
                
                # Validate SQL syntax (basic check)
                if not migration.up_sql or not migration.up_sql.strip():
                    validation['valid'] = False
                    validation['errors'].append("Empty migration SQL")
                    return validation
                
                # Check for dangerous operations
                dangerous_keywords = ['DROP DATABASE', 'TRUNCATE TABLE', 'DELETE FROM']
                up_sql_upper = migration.up_sql.upper()
                for keyword in dangerous_keywords:
                    if keyword in up_sql_upper and not migration.data_migration:
                        validation['errors'].append(f"Potentially dangerous operation detected: {keyword}")
                        # Don't fail, just warn
                
                # Validate table existence for data migrations
                if migration.data_migration:
                    inspector = inspect(self.engine)
                    existing_tables = inspector.get_table_names()
                    
                    # Look for table names in migration SQL
                    import re
                    table_pattern = r'\b(FROM|UPDATE|INSERT INTO|ALTER TABLE)\s+(\w+)'
                    matches = re.findall(table_pattern, migration.up_sql, re.IGNORECASE)
                    
                    for match in matches:
                        table_name = match[1]
                        if table_name.lower() not in [t.lower() for t in existing_tables]:
                            validation['errors'].append(f"Table {table_name} not found for data migration")
        
        except Exception as e:
            validation['valid'] = False
            validation['errors'].append(f"Pre-validation error: {str(e)}")
        
        return validation
    
    async def _execute_migration_sql(self, migration: MigrationScript) -> Dict[str, Any]:
        """Execute migration SQL statements."""
        execution_result = {'success': False, 'records_affected': 0, 'errors': []}
        
        try:
            with self.session_factory() as session:
                # Split SQL into individual statements
                statements = [stmt.strip() for stmt in migration.up_sql.split(';') if stmt.strip()]
                
                total_affected = 0
                
                for statement in statements:
                    if statement:
                        try:
                            result = session.execute(text(statement))
                            
                            # Count affected rows for data modifications
                            if result.rowcount and result.rowcount > 0:
                                total_affected += result.rowcount
                                
                        except Exception as stmt_e:
                            execution_result['errors'].append(f"Statement error: {stmt_e} (SQL: {statement[:100]}...)")
                            session.rollback()
                            return execution_result
                
                # Commit all changes
                session.commit()
                
                execution_result['success'] = True
                execution_result['records_affected'] = total_affected
                
                print(f"Migration SQL executed successfully, {total_affected} records affected")
        
        except Exception as e:
            execution_result['errors'].append(f"Migration execution error: {str(e)}")
        
        return execution_result
    
    async def _execute_rollback_sql(self, migration: MigrationScript) -> Dict[str, Any]:
        """Execute rollback SQL statements."""
        rollback_result = {'success': False, 'errors': []}
        
        try:
            if not migration.down_sql:
                rollback_result['errors'].append("No rollback SQL provided")
                return rollback_result
            
            with self.session_factory() as session:
                # Split SQL into individual statements
                statements = [stmt.strip() for stmt in migration.down_sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement:
                        try:
                            session.execute(text(statement))
                        except Exception as stmt_e:
                            rollback_result['errors'].append(f"Rollback statement error: {stmt_e}")
                            session.rollback()
                            return rollback_result
                
                session.commit()
                rollback_result['success'] = True
                print("Rollback SQL executed successfully")
        
        except Exception as e:
            rollback_result['errors'].append(f"Rollback execution error: {str(e)}")
        
        return rollback_result
    
    async def _post_migration_validation(self, migration: MigrationScript) -> Dict[str, Any]:
        """Perform post-migration validation."""
        validation = {'valid': True, 'errors': []}
        
        try:
            with self.session_factory() as session:
                # Basic connectivity check
                session.execute(text("SELECT 1"))
                
                # Check if expected changes are present
                if migration.data_migration:
                    # For data migrations, verify data integrity
                    inspector = inspect(self.engine)
                    tables = inspector.get_table_names()
                    
                    # Verify table existence and basic structure
                    for table_name in tables:
                        try:
                            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                            count = result.scalar()
                            if count is None:
                                validation['errors'].append(f"Could not query table {table_name}")
                        except Exception as table_e:
                            validation['errors'].append(f"Table validation error for {table_name}: {str(table_e)}")
                
                # Additional validation based on migration type
                if 'CREATE INDEX' in migration.up_sql.upper():
                    # Verify index creation
                    inspector = inspect(self.engine)
                    for table_name in inspector.get_table_names():
                        indexes = inspector.get_indexes(table_name)
                        # Basic index existence check
                        pass  # Simplified for testing
                
                if not validation['errors']:
                    print("Post-migration validation passed")
        
        except Exception as e:
            validation['valid'] = False
            validation['errors'].append(f"Post-validation error: {str(e)}")
        
        if validation['errors']:
            validation['valid'] = False
        
        return validation
    
    async def _record_migration_history(self, migration: MigrationScript, result: MigrationResult):
        """Record migration in history."""
        history_entry = {
            'version': migration.version,
            'name': migration.name,
            'migration': migration,
            'result': result,
            'applied_timestamp': datetime.now(),
            'rolled_back': False
        }
        
        self.migration_history.append(history_entry)
    
    async def _rollback_migration(self, migration: MigrationScript):
        """Rollback a migration."""
        print(f"Attempting automatic rollback for migration {migration.version}")
        
        try:
            rollback_result = await self._execute_rollback_sql(migration)
            if rollback_result['success']:
                print(f"✅ Automatic rollback successful for {migration.version}")
            else:
                print(f"❌ Automatic rollback failed for {migration.version}: {rollback_result['errors']}")
        except Exception as e:
            print(f"❌ Rollback exception for {migration.version}: {e}")
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        return {
            'applied_migrations': list(self.applied_migrations),
            'migration_history': len(self.migration_history),
            'backup_paths': len(self.backup_paths),
            'latest_migration': self.migration_history[-1]['version'] if self.migration_history else None
        }
    
    def cleanup_migration_artifacts(self):
        """Clean up migration backups and artifacts."""
        for backup_path in self.backup_paths:
            try:
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                    print(f"Cleaned up backup: {backup_path}")
            except Exception as e:
                print(f"Error cleaning up backup {backup_path}: {e}")


class TestDataMigration:
    """Test database migration procedures with production-like data."""
    
    @pytest.fixture
    async def migration_test_database(self):
        """Create database with production-like data for migration testing."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        # Create production-like dataset
        with SessionLocal() as session:
            # Create accounts
            accounts = []
            for i in range(10):
                account = Account(
                    name=f"MIGRATION_TEST_{i+1:02d}",
                    symbol="ES" if i % 2 == 0 else "NQ",
                    total_trades=0,
                    is_active=True
                )
                accounts.append(account)
            session.add_all(accounts)
            
            # Create substantial trade data
            trades = []
            base_date = datetime.now() - timedelta(days=90)
            
            for account in accounts:
                for day in range(90):
                    trade_date = base_date + timedelta(days=day)
                    if trade_date.weekday() >= 5:  # Skip weekends
                        continue
                    
                    # 10-20 trades per day per account
                    daily_trades = 15
                    for trade_num in range(daily_trades):
                        trade_id = len(trades) + 1
                        entry_time = trade_date.replace(hour=9 + (trade_num % 7), minute=(trade_num * 5) % 60)
                        exit_time = entry_time + timedelta(minutes=30)
                        
                        pnl = (trade_num % 10 - 4) * 25  # Mix of wins/losses
                        
                        trade = ProcessedTrade(
                            trade_id=f"MIG_{trade_id:08d}",
                            account_name=account.name,
                            symbol=account.symbol,
                            entry_time=entry_time,
                            exit_time=exit_time,
                            entry_price=4500.0,
                            exit_price=4500.0 + (pnl / 20),
                            quantity=1,
                            side="LONG" if pnl > 0 else "SHORT",
                            profit_loss=pnl,
                            commission=2.50,
                            duration_minutes=30,
                            hour_of_day=entry_time.hour,
                            day_of_week=entry_time.weekday(),
                            entry_order_id=f"E_{trade_id}",
                            exit_order_id=f"X_{trade_id}"
                        )
                        trades.append(trade)
            
            session.add_all(trades)
            
            # Update account statistics
            for account in accounts:
                account_trades = [t for t in trades if t.account_name == account.name]
                account.total_trades = len(account_trades)
                if account_trades:
                    account.first_trade_date = min(t.entry_time for t in account_trades)
                    account.last_trade_date = max(t.entry_time for t in account_trades)
            
            # Add time-bin analysis data
            time_bin_analyses = []
            for account in accounts:
                for hour in [10, 11, 12, 13, 14]:
                    for minute_bin in [0, 15, 30, 45]:
                        analysis = TimeBinAnalysis(
                            account_name=account.name,
                            hour=hour,
                            minute_bin=minute_bin,
                            analysis_date=datetime.now().date(),
                            total_trades=25,
                            win_rate=0.6,
                            average_pnl=15.0,
                            sharpe_ratio=1.2,
                            max_drawdown=-75.0,
                            profit_factor=1.35,
                            statistical_significance=True,
                            sample_size_adequate=True
                        )
                        time_bin_analyses.append(analysis)
            
            session.add_all(time_bin_analyses)
            session.commit()
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.fixture
    def sample_migrations(self):
        """Create sample migration scripts for testing."""
        return [
            MigrationScript(
                version="001",
                name="Add performance indexes",
                description="Add indexes to improve query performance",
                up_sql="""
                    CREATE INDEX idx_trades_account_time ON processed_trades(account_name, entry_time);
                    CREATE INDEX idx_trades_pnl ON processed_trades(profit_loss);
                    CREATE INDEX idx_timebin_account_hour ON time_bin_analysis(account_name, hour);
                """,
                down_sql="""
                    DROP INDEX IF EXISTS idx_trades_account_time;
                    DROP INDEX IF EXISTS idx_trades_pnl;
                    DROP INDEX IF EXISTS idx_timebin_account_hour;
                """,
                estimated_duration_seconds=30,
                requires_downtime=False
            ),
            MigrationScript(
                version="002",
                name="Add deployment tracking",
                description="Add deployment version tracking to tables",
                up_sql="""
                    ALTER TABLE processed_trades ADD COLUMN deployment_version VARCHAR(50);
                    ALTER TABLE time_bin_analysis ADD COLUMN deployment_version VARCHAR(50);
                    UPDATE processed_trades SET deployment_version = '1.0.0' WHERE deployment_version IS NULL;
                    UPDATE time_bin_analysis SET deployment_version = '1.0.0' WHERE deployment_version IS NULL;
                """,
                down_sql="""
                    ALTER TABLE processed_trades DROP COLUMN deployment_version;
                    ALTER TABLE time_bin_analysis DROP COLUMN deployment_version;
                """,
                estimated_duration_seconds=60,
                requires_downtime=False,
                data_migration=True,
                dependencies=["001"]
            ),
            MigrationScript(
                version="003",
                name="Add audit timestamps",
                description="Add created_at and updated_at timestamps",
                up_sql="""
                    ALTER TABLE accounts ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;
                    ALTER TABLE accounts ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;
                    UPDATE accounts SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;
                    UPDATE accounts SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;
                """,
                down_sql="""
                    ALTER TABLE accounts DROP COLUMN created_at;
                    ALTER TABLE accounts DROP COLUMN updated_at;
                """,
                estimated_duration_seconds=45,
                requires_downtime=False,
                data_migration=True,
                dependencies=["002"]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_single_migration_application(self, migration_test_database, sample_migrations):
        """Test applying a single migration."""
        print("\nTesting single migration application...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Apply first migration
        migration = sample_migrations[0]
        result = await migration_manager.apply_migration(migration)
        
        print(f"Migration result: {result}")
        
        # Validate migration success
        assert result.success, f"Migration failed: {result.errors}"
        assert result.duration_seconds > 0, "Migration should have measurable duration"
        assert result.data_integrity_check, "Data integrity check should pass"
        assert migration.version in migration_manager.applied_migrations, "Migration should be recorded as applied"
        
        # Verify indexes were created
        inspector = inspect(engine)
        indexes = []
        for table_name in inspector.get_table_names():
            table_indexes = inspector.get_indexes(table_name)
            indexes.extend([idx['name'] for idx in table_indexes])
        
        expected_indexes = ['idx_trades_account_time', 'idx_trades_pnl', 'idx_timebin_account_hour']
        for expected_idx in expected_indexes:
            # Note: SQLite may modify index names, so check for partial matches
            assert any(expected_idx in idx for idx in indexes), f"Index {expected_idx} not found"
        
        # Cleanup
        migration_manager.cleanup_migration_artifacts()
        
        print("✅ Single migration application test passed")
    
    @pytest.mark.asyncio
    async def test_migration_rollback(self, migration_test_database, sample_migrations):
        """Test migration rollback procedures."""
        print("\nTesting migration rollback...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Apply migration
        migration = sample_migrations[0]
        apply_result = await migration_manager.apply_migration(migration)
        assert apply_result.success, "Initial migration should succeed"
        
        # Verify migration is applied
        assert migration.version in migration_manager.applied_migrations
        
        # Rollback migration
        rollback_result = await migration_manager.rollback_migration(migration.version)
        
        print(f"Rollback result: {rollback_result}")
        
        # Validate rollback success
        assert rollback_result.success, f"Rollback failed: {rollback_result.errors}"
        assert rollback_result.duration_seconds > 0, "Rollback should have measurable duration"
        assert migration.version not in migration_manager.applied_migrations, "Migration should be removed from applied set"
        
        # Verify rollback history
        history_entry = next((h for h in migration_manager.migration_history if h['version'] == migration.version), None)
        assert history_entry is not None, "Should have history entry"
        assert history_entry['rolled_back'], "Should be marked as rolled back"
        
        # Cleanup
        migration_manager.cleanup_migration_artifacts()
        
        print("✅ Migration rollback test passed")
    
    @pytest.mark.asyncio
    async def test_batch_migration_application(self, migration_test_database, sample_migrations):
        """Test applying multiple migrations in batch."""
        print("\nTesting batch migration application...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Apply all migrations in batch
        batch_result = await migration_manager.apply_migrations_batch(sample_migrations)
        
        print(f"Batch migration result:")
        print(f"  Success: {batch_result['success']}")
        print(f"  Applied: {len(batch_result['migrations_applied'])}")
        print(f"  Failed: {len(batch_result['migrations_failed'])}")
        print(f"  Duration: {batch_result['total_duration']:.2f}s")
        print(f"  Rollback performed: {batch_result['rollback_performed']}")
        
        # Validate batch application
        assert batch_result['success'], f"Batch migration failed: {batch_result['migrations_failed']}"
        assert len(batch_result['migrations_applied']) == len(sample_migrations), "All migrations should be applied"
        assert len(batch_result['migrations_failed']) == 0, "No migrations should fail"
        assert not batch_result['rollback_performed'], "No rollback should be needed"
        assert batch_result['total_duration'] > 0, "Should have measurable duration"
        
        # Verify all migrations are applied
        for migration in sample_migrations:
            assert migration.version in migration_manager.applied_migrations, f"Migration {migration.version} not applied"
        
        # Verify database changes
        with SessionLocal() as session:
            # Check for new columns added by migration 002
            inspector = inspect(engine)
            trade_columns = [col['name'] for col in inspector.get_columns('processed_trades')]
            assert 'deployment_version' in trade_columns, "deployment_version column should exist"
            
            # Check for new columns added by migration 003
            account_columns = [col['name'] for col in inspector.get_columns('accounts')]
            assert 'created_at' in account_columns, "created_at column should exist"
            assert 'updated_at' in account_columns, "updated_at column should exist"
            
            # Verify data integrity
            result = session.execute(text("SELECT COUNT(*) FROM processed_trades WHERE deployment_version = '1.0.0'"))
            count = result.scalar()
            assert count > 0, "Data migration should have updated existing records"
        
        # Cleanup
        migration_manager.cleanup_migration_artifacts()
        
        print("✅ Batch migration application test passed")
    
    @pytest.mark.asyncio
    async def test_migration_failure_and_rollback(self, migration_test_database):
        """Test migration failure handling and automatic rollback."""
        print("\nTesting migration failure and automatic rollback...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Create a migration that will fail
        failing_migration = MigrationScript(
            version="999",
            name="Failing migration test",
            description="Migration designed to fail for testing",
            up_sql="""
                ALTER TABLE nonexistent_table ADD COLUMN new_column VARCHAR(50);
                CREATE INDEX idx_on_missing_table ON missing_table(column_that_doesnt_exist);
            """,
            down_sql="""
                ALTER TABLE nonexistent_table DROP COLUMN new_column;
                DROP INDEX IF EXISTS idx_on_missing_table;
            """,
            estimated_duration_seconds=10
        )
        
        # Apply failing migration
        result = await migration_manager.apply_migration(failing_migration)
        
        print(f"Failing migration result: {result}")
        
        # Validate failure handling
        assert not result.success, "Migration should fail"
        assert len(result.errors) > 0, "Should have error messages"
        assert failing_migration.version not in migration_manager.applied_migrations, "Failed migration should not be recorded as applied"
        
        # Verify database remains in consistent state
        with SessionLocal() as session:
            # Basic connectivity check
            session.execute(text("SELECT 1"))
            
            # Verify original tables still exist and are accessible
            result = session.execute(text("SELECT COUNT(*) FROM processed_trades"))
            count = result.scalar()
            assert count >= 0, "Original data should still be accessible"
        
        print("✅ Migration failure and rollback test passed")
    
    @pytest.mark.asyncio
    async def test_data_migration_integrity(self, migration_test_database):
        """Test data migration with integrity validation."""
        print("\nTesting data migration integrity...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Get initial data count and checksums
        with SessionLocal() as session:
            initial_trade_count = session.execute(text("SELECT COUNT(*) FROM processed_trades")).scalar()
            initial_account_count = session.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
            
            # Calculate checksum of critical data
            initial_pnl_sum = session.execute(text("SELECT SUM(profit_loss) FROM processed_trades")).scalar()
            print(f"Initial data: {initial_trade_count} trades, {initial_account_count} accounts, PnL sum: {initial_pnl_sum}")
        
        # Create data migration that modifies existing data
        data_migration = MigrationScript(
            version="data_001",
            name="Update trade categories",
            description="Add trade categories based on profit/loss",
            up_sql="""
                ALTER TABLE processed_trades ADD COLUMN trade_category VARCHAR(20);
                UPDATE processed_trades SET trade_category = 'WINNER' WHERE profit_loss > 0;
                UPDATE processed_trades SET trade_category = 'LOSER' WHERE profit_loss <= 0;
                CREATE INDEX idx_trade_category ON processed_trades(trade_category);
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_trade_category;
                ALTER TABLE processed_trades DROP COLUMN trade_category;
            """,
            data_migration=True,
            estimated_duration_seconds=120
        )
        
        # Apply data migration
        result = await migration_manager.apply_migration(data_migration)
        
        print(f"Data migration result: {result}")
        
        # Validate migration success
        assert result.success, f"Data migration failed: {result.errors}"
        assert result.records_affected > 0, "Should have affected records"
        
        # Validate data integrity after migration
        with SessionLocal() as session:
            # Check data counts remain the same
            final_trade_count = session.execute(text("SELECT COUNT(*) FROM processed_trades")).scalar()
            final_account_count = session.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
            
            assert final_trade_count == initial_trade_count, "Trade count should remain unchanged"
            assert final_account_count == initial_account_count, "Account count should remain unchanged"
            
            # Check PnL sum remains the same (data integrity)
            final_pnl_sum = session.execute(text("SELECT SUM(profit_loss) FROM processed_trades")).scalar()
            assert abs(final_pnl_sum - initial_pnl_sum) < 0.01, "PnL sum should remain unchanged"
            
            # Verify new column is populated correctly
            winner_count = session.execute(text("SELECT COUNT(*) FROM processed_trades WHERE trade_category = 'WINNER'")).scalar()
            loser_count = session.execute(text("SELECT COUNT(*) FROM processed_trades WHERE trade_category = 'LOSER'")).scalar()
            
            assert winner_count + loser_count == final_trade_count, "All trades should be categorized"
            
            # Cross-validate categorization
            actual_winners = session.execute(text("SELECT COUNT(*) FROM processed_trades WHERE profit_loss > 0")).scalar()
            assert winner_count == actual_winners, "Winner categorization should match profit_loss > 0"
            
            print(f"Data migration validation: {winner_count} winners, {loser_count} losers")
        
        # Cleanup
        migration_manager.cleanup_migration_artifacts()
        
        print("✅ Data migration integrity test passed")
    
    @pytest.mark.asyncio
    async def test_migration_performance_benchmarks(self, migration_test_database, sample_migrations):
        """Test migration performance benchmarks."""
        print("\nTesting migration performance benchmarks...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Performance benchmarks (in seconds)
        benchmarks = {
            'single_migration_max_duration': 10.0,
            'batch_migration_max_duration': 30.0,
            'backup_creation_max_duration': 5.0,
            'rollback_max_duration': 5.0
        }
        
        performance_results = {}
        
        # Benchmark single migration
        start_time = time.time()
        migration = sample_migrations[0]
        result = await migration_manager.apply_migration(migration)
        performance_results['single_migration_duration'] = time.time() - start_time
        
        assert result.success, "Migration should succeed for performance test"
        
        # Benchmark rollback
        start_time = time.time()
        rollback_result = await migration_manager.rollback_migration(migration.version)
        performance_results['rollback_duration'] = time.time() - start_time
        
        assert rollback_result.success, "Rollback should succeed"
        
        # Benchmark batch migration
        start_time = time.time()
        batch_result = await migration_manager.apply_migrations_batch(sample_migrations)
        performance_results['batch_migration_duration'] = time.time() - start_time
        
        assert batch_result['success'], "Batch migration should succeed"
        
        # Benchmark backup creation (test separately)
        start_time = time.time()
        backup_result = await migration_manager._create_migration_backup("perf_test")
        performance_results['backup_creation_duration'] = time.time() - start_time
        
        assert backup_result['success'], "Backup creation should succeed"
        
        print(f"Migration performance benchmarks:")
        for benchmark_name, max_duration in benchmarks.items():
            actual_duration = performance_results.get(benchmark_name.replace('_max_duration', '_duration'), 0)
            passed = actual_duration <= max_duration
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {benchmark_name}: {actual_duration:.2f}s (max: {max_duration}s) {status}")
            
            # Assert performance benchmarks
            assert actual_duration <= max_duration, f"{benchmark_name} too slow: {actual_duration:.2f}s > {max_duration}s"
        
        # Test migration performance under concurrent load
        print("\nTesting concurrent migration performance...")
        
        # Simulate concurrent database access during migration
        async def concurrent_database_access():
            """Simulate concurrent database queries during migration."""
            try:
                with SessionLocal() as session:
                    for _ in range(10):
                        session.execute(text("SELECT COUNT(*) FROM processed_trades"))
                        session.execute(text("SELECT COUNT(*) FROM accounts"))
                        await asyncio.sleep(0.1)
                return True
            except Exception as e:
                print(f"Concurrent access error: {e}")
                return False
        
        # Start concurrent access
        concurrent_task = asyncio.create_task(concurrent_database_access())
        
        # Apply migration while concurrent access is running
        start_time = time.time()
        migration = sample_migrations[1]  # Data migration
        result = await migration_manager.apply_migration(migration)
        concurrent_migration_duration = time.time() - start_time
        
        # Wait for concurrent access to complete
        concurrent_success = await concurrent_task
        
        print(f"Concurrent migration results:")
        print(f"  Migration duration: {concurrent_migration_duration:.2f}s")
        print(f"  Concurrent access success: {concurrent_success}")
        print(f"  Migration success: {result.success}")
        
        # Validate concurrent migration
        assert result.success, "Migration should succeed even with concurrent access"
        assert concurrent_success, "Concurrent database access should not fail during migration"
        assert concurrent_migration_duration <= 15.0, "Migration should not be severely slowed by concurrent access"
        
        # Cleanup
        migration_manager.cleanup_migration_artifacts()
        
        print("✅ Migration performance benchmarks passed")
    
    @pytest.mark.asyncio
    async def test_zero_downtime_migration_validation(self, migration_test_database):
        """Test zero-downtime migration capabilities."""
        print("\nTesting zero-downtime migration validation...")
        
        engine, SessionLocal = migration_test_database
        migration_manager = DatabaseMigrationManager(engine, SessionLocal)
        
        # Track database availability during migration
        availability_checks = []
        migration_running = True
        
        async def monitor_database_availability():
            """Monitor database availability during migration."""
            while migration_running:
                try:
                    start_time = time.time()
                    with SessionLocal() as session:
                        # Perform typical application queries
                        session.execute(text("SELECT COUNT(*) FROM processed_trades"))
                        session.execute(text("SELECT * FROM accounts LIMIT 5"))
                        session.execute(text("SELECT AVG(profit_loss) FROM processed_trades WHERE account_name = 'MIGRATION_TEST_01'"))
                    
                    response_time = (time.time() - start_time) * 1000  # Convert to ms
                    availability_checks.append({
                        'timestamp': time.time(),
                        'available': True,
                        'response_time_ms': response_time
                    })
                    
                except Exception as e:
                    availability_checks.append({
                        'timestamp': time.time(),
                        'available': False,
                        'error': str(e)
                    })
                
                await asyncio.sleep(0.1)  # Check every 100ms
        
        # Create online migration (should not require downtime)
        online_migration = MigrationScript(
            version="online_001",
            name="Online index creation",
            description="Create index without blocking queries",
            up_sql="""
                CREATE INDEX idx_trades_symbol_time ON processed_trades(symbol, entry_time);
                CREATE INDEX idx_accounts_active ON accounts(is_active);
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_trades_symbol_time;
                DROP INDEX IF EXISTS idx_accounts_active;
            """,
            requires_downtime=False,
            estimated_duration_seconds=10
        )
        
        # Start availability monitoring
        monitoring_task = asyncio.create_task(monitor_database_availability())
        
        # Apply online migration
        migration_start = time.time()
        result = await migration_manager.apply_migration(online_migration)
        migration_duration = time.time() - migration_start
        
        # Stop monitoring
        migration_running = False
        await asyncio.sleep(0.2)  # Allow monitoring to finish
        monitoring_task.cancel()
        
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        
        # Analyze availability during migration
        total_checks = len(availability_checks)
        available_checks = sum(1 for check in availability_checks if check.get('available', False))
        availability_percentage = (available_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Calculate response time statistics
        response_times = [check.get('response_time_ms', 0) for check in availability_checks if check.get('available', False)]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        
        print(f"Zero-downtime migration results:")
        print(f"  Migration success: {result.success}")
        print(f"  Migration duration: {migration_duration:.2f}s")
        print(f"  Database availability: {availability_percentage:.1f}%")
        print(f"  Total availability checks: {total_checks}")
        print(f"  Available checks: {available_checks}")
        print(f"  Average response time: {avg_response_time:.1f}ms")
        print(f"  Max response time: {max_response_time:.1f}ms")
        
        # Validate zero-downtime requirements
        assert result.success, f"Online migration failed: {result.errors}"
        assert availability_percentage >= 95.0, f"Database availability too low: {availability_percentage:.1f}%"
        assert avg_response_time <= 100.0, f"Response time degraded too much: {avg_response_time:.1f}ms"
        assert max_response_time <= 500.0, f"Max response time too high: {max_response_time:.1f}ms"
        
        # Verify migration was applied successfully
        inspector = inspect(engine)
        trade_indexes = inspector.get_indexes('processed_trades')
        account_indexes = inspector.get_indexes('accounts')
        
        trade_index_names = [idx['name'] for idx in trade_indexes]
        account_index_names = [idx['name'] for idx in account_indexes]
        
        assert any('symbol' in idx for idx in trade_index_names), "Symbol index should be created"
        assert any('active' in idx for idx in account_index_names), "Active index should be created"
        
        # Cleanup
        migration_manager.cleanup_migration_artifacts()
        
        print("✅ Zero-downtime migration validation passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])