"""
High-performance caching system for analytics and computation optimization.

This module provides advanced caching capabilities for trading analytics,
including multi-level caching, intelligent cache warming, and performance optimization.

Requirements: 10.2, 10.3, 11.1
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import pickle
import json
import zlib
import time
import threading
from pathlib import Path
import sqlite3
import redis
from collections import OrderedDict
import weakref
import psutil

from ..time_bin_analyzer import TimeBin
from ...models.trading import ProcessedTrade

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache level hierarchy."""
    MEMORY_L1 = "memory_l1"  # Hot cache - fastest access
    MEMORY_L2 = "memory_l2"  # Warm cache - medium access
    DISK_L3 = "disk_l3"      # Cold cache - persistent storage
    REDIS_L4 = "redis_l4"    # Distributed cache
    DATABASE_L5 = "database_l5"  # Long-term storage


class CacheStrategy(Enum):
    """Cache replacement strategy."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    TTL = "ttl"  # Time To Live
    ADAPTIVE = "adaptive"  # Adaptive replacement


class CompressionLevel(Enum):
    """Compression level for cached data."""
    NONE = 0
    FAST = 1
    BALANCED = 3
    MAXIMUM = 9


@dataclass
class CacheConfiguration:
    """Configuration for cache management."""
    # Memory cache settings
    l1_max_size_mb: float = 256.0  # 256MB L1 cache
    l2_max_size_mb: float = 1024.0  # 1GB L2 cache
    max_memory_usage_percent: float = 50.0  # % of system memory
    
    # Disk cache settings
    disk_cache_dir: str = "./cache"
    disk_max_size_gb: float = 10.0  # 10GB disk cache
    
    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_max_connections: int = 10
    
    # Cache behavior
    default_ttl_seconds: int = 3600  # 1 hour
    compression_level: CompressionLevel = CompressionLevel.BALANCED
    cache_strategy: CacheStrategy = CacheStrategy.ADAPTIVE
    
    # Performance settings
    async_writes: bool = True
    batch_size: int = 100
    warming_threads: int = 2
    
    # Monitoring
    enable_metrics: bool = True
    metrics_interval_seconds: int = 60


@dataclass
class CacheEntry:
    """Individual cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    size_bytes: int
    ttl_seconds: Optional[int] = None
    compression_used: bool = False
    cache_level: CacheLevel = CacheLevel.MEMORY_L1
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds is None:
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time
    
    def update_access(self):
        """Update access statistics."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    # Hit/miss statistics
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Level-specific metrics
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    l4_hits: int = 0
    
    # Performance metrics
    average_lookup_time_ms: float = 0.0
    average_write_time_ms: float = 0.0
    
    # Memory usage
    l1_usage_mb: float = 0.0
    l2_usage_mb: float = 0.0
    total_memory_usage_mb: float = 0.0
    
    # Disk usage
    disk_usage_gb: float = 0.0
    
    # Operations
    evictions: int = 0
    compressions: int = 0
    decompressions: int = 0
    
    # Timing
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate


class LRUCache:
    """Thread-safe LRU cache implementation."""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get item from cache."""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired():
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    entry.update_access()
                    return entry
                else:
                    # Remove expired entry
                    del self.cache[key]
            return None
    
    def put(self, key: str, entry: CacheEntry):
        """Put item in cache."""
        with self.lock:
            if key in self.cache:
                # Update existing entry
                self.cache[key] = entry
                self.cache.move_to_end(key)
            else:
                # Add new entry
                if len(self.cache) >= self.max_size:
                    # Remove least recently used
                    self.cache.popitem(last=False)
                self.cache[key] = entry
    
    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all items from cache."""
        with self.lock:
            self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        with self.lock:
            return len(self.cache)
    
    def get_memory_usage(self) -> float:
        """Get memory usage in MB."""
        with self.lock:
            total_bytes = sum(entry.size_bytes for entry in self.cache.values())
            return total_bytes / (1024 * 1024)


class DiskCache:
    """Persistent disk cache with SQLite backend."""
    
    def __init__(self, cache_dir: str, max_size_gb: float):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_gb = max_size_gb
        
        # Initialize SQLite database for metadata
        self.db_path = self.cache_dir / "cache_metadata.db"
        self._init_database()
        
        self.lock = threading.RLock()
    
    def _init_database(self):
        """Initialize SQLite database for cache metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL,
                    access_count INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    ttl_seconds INTEGER,
                    compressed BOOLEAN NOT NULL
                )
            """)
            
            # Create index for efficient lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)")
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from disk cache."""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT file_path, ttl_seconds, created_at, compressed FROM cache_entries WHERE key = ?",
                        (key,)
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        file_path, ttl_seconds, created_at_str, compressed = row
                        created_at = datetime.fromisoformat(created_at_str)
                        
                        # Check expiration
                        if ttl_seconds and (datetime.now() - created_at).total_seconds() > ttl_seconds:
                            self.remove(key)
                            return None
                        
                        # Load data from file
                        file_path = self.cache_dir / file_path
                        if file_path.exists():
                            with open(file_path, 'rb') as f:
                                data = f.read()
                                
                            if compressed:
                                data = zlib.decompress(data)
                            
                            value = pickle.loads(data)
                            
                            # Update access time
                            conn.execute(
                                "UPDATE cache_entries SET last_accessed = ?, access_count = access_count + 1 WHERE key = ?",
                                (datetime.now().isoformat(), key)
                            )
                            
                            return value
                        else:
                            # File missing, remove metadata
                            self.remove(key)
                
                return None
                
            except Exception as e:
                logger.error(f"Failed to get from disk cache: {str(e)}")
                return None
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None, compress: bool = True):
        """Put item in disk cache."""
        with self.lock:
            try:
                # Serialize value
                data = pickle.dumps(value)
                original_size = len(data)
                
                # Compress if requested
                if compress:
                    data = zlib.compress(data)
                
                # Generate unique file name
                file_name = f"{hashlib.md5(key.encode()).hexdigest()}.cache"
                file_path = self.cache_dir / file_name
                
                # Write to file
                with open(file_path, 'wb') as f:
                    f.write(data)
                
                # Update metadata
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries 
                        (key, file_path, created_at, last_accessed, access_count, size_bytes, ttl_seconds, compressed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        key, file_name, datetime.now().isoformat(), datetime.now().isoformat(),
                        0, original_size, ttl_seconds, compress
                    ))
                
                # Check if cleanup is needed
                asyncio.create_task(self._cleanup_if_needed())
                
            except Exception as e:
                logger.error(f"Failed to put in disk cache: {str(e)}")
    
    def remove(self, key: str) -> bool:
        """Remove item from disk cache."""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT file_path FROM cache_entries WHERE key = ?", (key,))
                    row = cursor.fetchone()
                    
                    if row:
                        file_path = self.cache_dir / row[0]
                        if file_path.exists():
                            file_path.unlink()
                        
                        conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                        return True
                
                return False
                
            except Exception as e:
                logger.error(f"Failed to remove from disk cache: {str(e)}")
                return False
    
    def clear(self):
        """Clear all items from disk cache."""
        with self.lock:
            try:
                # Remove all cache files
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink()
                
                # Clear metadata
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM cache_entries")
                
            except Exception as e:
                logger.error(f"Failed to clear disk cache: {str(e)}")
    
    def get_usage_gb(self) -> float:
        """Get current disk usage in GB."""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.cache"))
            return total_size / (1024 ** 3)
        except Exception:
            return 0.0
    
    async def _cleanup_if_needed(self):
        """Cleanup disk cache if size limit exceeded."""
        current_size = self.get_usage_gb()
        
        if current_size > self.max_size_gb:
            # Remove oldest entries until under limit
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT key, file_path, size_bytes 
                    FROM cache_entries 
                    ORDER BY last_accessed ASC
                """)
                
                bytes_to_remove = (current_size - self.max_size_gb * 0.8) * (1024 ** 3)  # Remove to 80% capacity
                bytes_removed = 0
                
                for row in cursor:
                    if bytes_removed >= bytes_to_remove:
                        break
                    
                    key, file_path, size_bytes = row
                    if self.remove(key):
                        bytes_removed += size_bytes


class RedisCache:
    """Redis-based distributed cache."""
    
    def __init__(self, config: CacheConfiguration):
        self.config = config
        self.redis_client = None
        self._connection_pool = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            import redis
            
            self._connection_pool = redis.ConnectionPool(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                max_connections=self.config.redis_max_connections
            )
            
            self.redis_client = redis.Redis(connection_pool=self._connection_pool)
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
            
        except Exception as e:
            logger.warning(f"Redis cache initialization failed: {str(e)}")
            self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from Redis cache."""
        if not self.redis_client:
            return None
        
        try:
            data = self.redis_client.get(key)
            if data:
                # Decompress and deserialize
                if self.config.compression_level != CompressionLevel.NONE:
                    data = zlib.decompress(data)
                return pickle.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get from Redis cache: {str(e)}")
            return None
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Put item in Redis cache."""
        if not self.redis_client:
            return
        
        try:
            # Serialize value
            data = pickle.dumps(value)
            
            # Compress if configured
            if self.config.compression_level != CompressionLevel.NONE:
                data = zlib.compress(data, self.config.compression_level.value)
            
            # Set with TTL
            if ttl_seconds:
                self.redis_client.setex(key, ttl_seconds, data)
            else:
                self.redis_client.set(key, data)
                
        except Exception as e:
            logger.error(f"Failed to put in Redis cache: {str(e)}")
    
    def remove(self, key: str) -> bool:
        """Remove item from Redis cache."""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Failed to remove from Redis cache: {str(e)}")
            return False
    
    def clear(self):
        """Clear Redis cache."""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.flushdb()
        except Exception as e:
            logger.error(f"Failed to clear Redis cache: {str(e)}")


class AnalyticsCacheManager:
    """
    High-performance multi-level cache manager for analytics.
    
    Provides intelligent caching with automatic cache warming, compression,
    and multi-level storage hierarchy for optimal performance.
    """
    
    def __init__(self, config: Optional[CacheConfiguration] = None):
        """Initialize the cache manager."""
        self.config = config or CacheConfiguration()
        
        # Initialize cache levels
        self.l1_cache = LRUCache(max_size=int(self.config.l1_max_size_mb * 1024 * 1024 / 1000))  # Estimate entries
        self.l2_cache = LRUCache(max_size=int(self.config.l2_max_size_mb * 1024 * 1024 / 10000))  # Larger entries
        self.disk_cache = DiskCache(self.config.disk_cache_dir, self.config.disk_max_size_gb)
        self.redis_cache = RedisCache(self.config) if self.config.redis_host else None
        
        # Metrics and monitoring
        self.metrics = CacheMetrics()
        self._metrics_lock = threading.RLock()
        
        # Background tasks
        self._warming_executor = None
        self._metrics_task = None
        self._cleanup_task = None
        
        # Key mapping for cache hierarchy
        self._key_locations: Dict[str, List[CacheLevel]] = {}
        self._key_lock = threading.RLock()
        
        # Start background tasks
        if self.config.enable_metrics:
            self._start_background_tasks()
        
        logger.info("AnalyticsCacheManager initialized with multi-level caching")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache with automatic level promotion.
        
        Searches through cache hierarchy and promotes frequently accessed
        items to higher-performance levels.
        """
        start_time = time.time()
        
        try:
            # Track request
            with self._metrics_lock:
                self.metrics.total_requests += 1
            
            # Try L1 cache first (fastest)
            entry = self.l1_cache.get(key)
            if entry and not entry.is_expired():
                with self._metrics_lock:
                    self.metrics.cache_hits += 1
                    self.metrics.l1_hits += 1
                return entry.value
            
            # Try L2 cache
            entry = self.l2_cache.get(key)
            if entry and not entry.is_expired():
                # Promote to L1 if frequently accessed
                if entry.access_count > 5:
                    await self._promote_to_l1(key, entry.value)
                
                with self._metrics_lock:
                    self.metrics.cache_hits += 1
                    self.metrics.l2_hits += 1
                return entry.value
            
            # Try disk cache
            value = self.disk_cache.get(key)
            if value is not None:
                # Promote to memory cache
                await self._promote_to_memory(key, value)
                
                with self._metrics_lock:
                    self.metrics.cache_hits += 1
                    self.metrics.l3_hits += 1
                return value
            
            # Try Redis cache
            if self.redis_cache:
                value = self.redis_cache.get(key)
                if value is not None:
                    # Promote to local caches
                    await self._promote_to_memory(key, value)
                    
                    with self._metrics_lock:
                        self.metrics.cache_hits += 1
                        self.metrics.l4_hits += 1
                    return value
            
            # Cache miss
            with self._metrics_lock:
                self.metrics.cache_misses += 1
            
            return default
            
        finally:
            # Update lookup time metrics
            lookup_time = (time.time() - start_time) * 1000  # ms
            with self._metrics_lock:
                if self.metrics.total_requests > 0:
                    # Moving average
                    self.metrics.average_lookup_time_ms = (
                        (self.metrics.average_lookup_time_ms * (self.metrics.total_requests - 1) + lookup_time) /
                        self.metrics.total_requests
                    )
    
    async def put(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        cache_levels: Optional[List[CacheLevel]] = None,
        priority: str = "normal"
    ):
        """
        Put value in cache with intelligent level selection.
        
        Automatically determines optimal cache levels based on value size,
        access patterns, and priority.
        """
        start_time = time.time()
        
        try:
            ttl = ttl_seconds or self.config.default_ttl_seconds
            
            # Determine cache levels if not specified
            if cache_levels is None:
                cache_levels = self._determine_optimal_levels(value, priority)
            
            # Calculate value size for metrics
            value_size = len(pickle.dumps(value))
            
            # Store in specified cache levels
            tasks = []
            
            for level in cache_levels:
                if level == CacheLevel.MEMORY_L1:
                    tasks.append(self._put_l1(key, value, ttl, value_size))
                elif level == CacheLevel.MEMORY_L2:
                    tasks.append(self._put_l2(key, value, ttl, value_size))
                elif level == CacheLevel.DISK_L3:
                    tasks.append(self._put_disk(key, value, ttl))
                elif level == CacheLevel.REDIS_L4:
                    tasks.append(self._put_redis(key, value, ttl))
            
            # Execute puts asynchronously or synchronously based on config
            if self.config.async_writes:
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                for task in tasks:
                    await task
            
            # Update key location tracking
            with self._key_lock:
                self._key_locations[key] = cache_levels
            
        finally:
            # Update write time metrics
            write_time = (time.time() - start_time) * 1000  # ms
            with self._metrics_lock:
                # Moving average
                total_writes = self.metrics.cache_hits + self.metrics.cache_misses  # Approximation
                if total_writes > 0:
                    self.metrics.average_write_time_ms = (
                        (self.metrics.average_write_time_ms * (total_writes - 1) + write_time) /
                        total_writes
                    )
    
    async def remove(self, key: str) -> bool:
        """Remove value from all cache levels."""
        removed = False
        
        # Remove from all levels
        tasks = [
            self._remove_l1(key),
            self._remove_l2(key),
            self._remove_disk(key),
            self._remove_redis(key)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        removed = any(r for r in results if isinstance(r, bool) and r)
        
        # Update key location tracking
        with self._key_lock:
            self._key_locations.pop(key, None)
        
        return removed
    
    async def clear(self, levels: Optional[List[CacheLevel]] = None):
        """Clear specified cache levels or all levels."""
        if levels is None:
            levels = list(CacheLevel)
        
        tasks = []
        for level in levels:
            if level == CacheLevel.MEMORY_L1:
                tasks.append(self._clear_l1())
            elif level == CacheLevel.MEMORY_L2:
                tasks.append(self._clear_l2())
            elif level == CacheLevel.DISK_L3:
                tasks.append(self._clear_disk())
            elif level == CacheLevel.REDIS_L4:
                tasks.append(self._clear_redis())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clear key tracking
        with self._key_lock:
            self._key_locations.clear()
    
    async def warm_cache(
        self,
        cache_warming_functions: List[Callable[[], Tuple[str, Any]]],
        batch_size: Optional[int] = None
    ):
        """
        Warm cache with pre-computed values.
        
        Executes warming functions to pre-populate cache with frequently
        accessed data for optimal performance.
        """
        logger.info(f"Starting cache warming with {len(cache_warming_functions)} functions")
        
        batch_size = batch_size or self.config.batch_size
        
        # Process warming functions in batches
        for i in range(0, len(cache_warming_functions), batch_size):
            batch = cache_warming_functions[i:i + batch_size]
            
            # Execute batch in parallel
            tasks = []
            for warming_func in batch:
                tasks.append(self._execute_warming_function(warming_func))
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results in cache
            for result in batch_results:
                if isinstance(result, tuple) and len(result) == 2:
                    key, value = result
                    await self.put(key, value, priority="high")
        
        logger.info("Cache warming completed")
    
    def get_metrics(self) -> CacheMetrics:
        """Get current cache metrics."""
        with self._metrics_lock:
            # Update memory usage
            self.metrics.l1_usage_mb = self.l1_cache.get_memory_usage()
            self.metrics.l2_usage_mb = self.l2_cache.get_memory_usage()
            self.metrics.total_memory_usage_mb = self.metrics.l1_usage_mb + self.metrics.l2_usage_mb
            self.metrics.disk_usage_gb = self.disk_cache.get_usage_gb()
            
            return self.metrics
    
    async def optimize_cache(self):
        """
        Optimize cache performance.
        
        Analyzes access patterns and reorganizes cache for better performance.
        """
        logger.info("Starting cache optimization")
        
        # Analyze access patterns
        access_patterns = await self._analyze_access_patterns()
        
        # Promote frequently accessed items
        await self._optimize_promotions(access_patterns)
        
        # Clean up expired entries
        await self._cleanup_expired_entries()
        
        # Rebalance cache levels
        await self._rebalance_cache_levels()
        
        logger.info("Cache optimization completed")
    
    def create_cache_key(self, *components: Any) -> str:
        """
        Create a deterministic cache key from components.
        
        Generates consistent cache keys for complex objects and parameters.
        """
        # Convert components to strings and hash
        key_data = "|".join(str(component) for component in components)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def cache_decorator(
        self,
        ttl_seconds: Optional[int] = None,
        key_prefix: str = "",
        cache_levels: Optional[List[CacheLevel]] = None
    ):
        """
        Decorator for automatic function result caching.
        
        Caches function results based on arguments and provides
        automatic cache invalidation.
        """
        def decorator(func: Callable):
            async def wrapper(*args, **kwargs):
                # Generate cache key
                key_components = [key_prefix, func.__name__] + list(args) + list(kwargs.items())
                cache_key = self.create_cache_key(*key_components)
                
                # Try to get from cache
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function and cache result
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                await self.put(cache_key, result, ttl_seconds, cache_levels)
                
                return result
            
            return wrapper
        return decorator
    
    # Private methods
    def _determine_optimal_levels(self, value: Any, priority: str) -> List[CacheLevel]:
        """Determine optimal cache levels for a value."""
        value_size = len(pickle.dumps(value))
        levels = []
        
        # Always use L1 for small, high-priority items
        if value_size < 1024 * 10 or priority == "high":  # 10KB
            levels.append(CacheLevel.MEMORY_L1)
        
        # Use L2 for medium-sized items
        if value_size < 1024 * 100:  # 100KB
            levels.append(CacheLevel.MEMORY_L2)
        
        # Use disk for larger items or persistent storage
        if value_size > 1024 * 50 or priority in ["persistent", "low"]:  # 50KB
            levels.append(CacheLevel.DISK_L3)
        
        # Use Redis for distributed caching
        if self.redis_cache and priority in ["high", "distributed"]:
            levels.append(CacheLevel.REDIS_L4)
        
        return levels or [CacheLevel.MEMORY_L2]  # Default fallback
    
    async def _promote_to_l1(self, key: str, value: Any):
        """Promote value to L1 cache."""
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            size_bytes=len(pickle.dumps(value)),
            cache_level=CacheLevel.MEMORY_L1
        )
        self.l1_cache.put(key, entry)
    
    async def _promote_to_memory(self, key: str, value: Any):
        """Promote value to memory caches."""
        await self._promote_to_l1(key, value)
        
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            size_bytes=len(pickle.dumps(value)),
            cache_level=CacheLevel.MEMORY_L2
        )
        self.l2_cache.put(key, entry)
    
    async def _put_l1(self, key: str, value: Any, ttl: int, size: int):
        """Put value in L1 cache."""
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=0,
            size_bytes=size,
            ttl_seconds=ttl,
            cache_level=CacheLevel.MEMORY_L1
        )
        self.l1_cache.put(key, entry)
    
    async def _put_l2(self, key: str, value: Any, ttl: int, size: int):
        """Put value in L2 cache."""
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=0,
            size_bytes=size,
            ttl_seconds=ttl,
            cache_level=CacheLevel.MEMORY_L2
        )
        self.l2_cache.put(key, entry)
    
    async def _put_disk(self, key: str, value: Any, ttl: int):
        """Put value in disk cache."""
        compress = self.config.compression_level != CompressionLevel.NONE
        self.disk_cache.put(key, value, ttl, compress)
    
    async def _put_redis(self, key: str, value: Any, ttl: int):
        """Put value in Redis cache."""
        if self.redis_cache:
            self.redis_cache.put(key, value, ttl)
    
    async def _remove_l1(self, key: str) -> bool:
        """Remove from L1 cache."""
        return self.l1_cache.remove(key)
    
    async def _remove_l2(self, key: str) -> bool:
        """Remove from L2 cache."""
        return self.l2_cache.remove(key)
    
    async def _remove_disk(self, key: str) -> bool:
        """Remove from disk cache."""
        return self.disk_cache.remove(key)
    
    async def _remove_redis(self, key: str) -> bool:
        """Remove from Redis cache."""
        if self.redis_cache:
            return self.redis_cache.remove(key)
        return False
    
    async def _clear_l1(self):
        """Clear L1 cache."""
        self.l1_cache.clear()
    
    async def _clear_l2(self):
        """Clear L2 cache."""
        self.l2_cache.clear()
    
    async def _clear_disk(self):
        """Clear disk cache."""
        self.disk_cache.clear()
    
    async def _clear_redis(self):
        """Clear Redis cache."""
        if self.redis_cache:
            self.redis_cache.clear()
    
    async def _execute_warming_function(self, warming_func: Callable) -> Tuple[str, Any]:
        """Execute a cache warming function."""
        try:
            if asyncio.iscoroutinefunction(warming_func):
                return await warming_func()
            else:
                return warming_func()
        except Exception as e:
            logger.error(f"Cache warming function failed: {str(e)}")
            return ("", None)
    
    async def _analyze_access_patterns(self) -> Dict[str, Any]:
        """Analyze cache access patterns for optimization."""
        # This would analyze actual access patterns
        # For now, return placeholder data
        return {
            "hot_keys": [],
            "cold_keys": [],
            "access_frequency": {},
            "size_distribution": {}
        }
    
    async def _optimize_promotions(self, access_patterns: Dict[str, Any]):
        """Optimize cache promotions based on access patterns."""
        # Implement promotion optimization logic
        pass
    
    async def _cleanup_expired_entries(self):
        """Clean up expired cache entries."""
        # Implement expired entry cleanup
        pass
    
    async def _rebalance_cache_levels(self):
        """Rebalance items across cache levels."""
        # Implement cache level rebalancing
        pass
    
    def _start_background_tasks(self):
        """Start background monitoring and maintenance tasks."""
        self._metrics_task = asyncio.create_task(self._metrics_collection_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _metrics_collection_loop(self):
        """Background metrics collection loop."""
        while True:
            try:
                await asyncio.sleep(self.config.metrics_interval_seconds)
                
                # Update system metrics
                with self._metrics_lock:
                    self.metrics.last_updated = datetime.now()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {str(e)}")
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                
                # Perform periodic cleanup
                await self._cleanup_expired_entries()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {str(e)}")
    
    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, '_metrics_task') and self._metrics_task:
            self._metrics_task.cancel()
        if hasattr(self, '_cleanup_task') and self._cleanup_task:
            self._cleanup_task.cancel()


# Factory functions
def create_cache_manager(
    memory_size_mb: float = 512.0,
    disk_size_gb: float = 5.0,
    redis_config: Optional[Dict[str, Any]] = None
) -> AnalyticsCacheManager:
    """Create a cache manager with specified configuration."""
    config = CacheConfiguration(
        l1_max_size_mb=memory_size_mb * 0.3,  # 30% for L1
        l2_max_size_mb=memory_size_mb * 0.7,  # 70% for L2
        disk_max_size_gb=disk_size_gb
    )
    
    if redis_config:
        config.redis_host = redis_config.get('host', 'localhost')
        config.redis_port = redis_config.get('port', 6379)
        config.redis_password = redis_config.get('password')
    
    return AnalyticsCacheManager(config)


def cache_time_bin_analytics(
    cache_manager: AnalyticsCacheManager,
    ttl_hours: int = 4
):
    """Decorator for caching time-bin analytics results."""
    return cache_manager.cache_decorator(
        ttl_seconds=ttl_hours * 3600,
        key_prefix="time_bin_analytics",
        cache_levels=[CacheLevel.MEMORY_L1, CacheLevel.DISK_L3]
    )


def cache_monte_carlo_results(
    cache_manager: AnalyticsCacheManager,
    ttl_hours: int = 24
):
    """Decorator for caching Monte Carlo simulation results."""
    return cache_manager.cache_decorator(
        ttl_seconds=ttl_hours * 3600,
        key_prefix="monte_carlo",
        cache_levels=[CacheLevel.MEMORY_L2, CacheLevel.DISK_L3, CacheLevel.REDIS_L4]
    )