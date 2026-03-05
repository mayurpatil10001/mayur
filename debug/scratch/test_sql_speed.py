from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import time

DB_URL = "sqlite:///./trading_platform.db"

def test_sqlalchemy_speed():
    print(f"Testing {DB_URL} with SQLAlchemy...")
    start_total = time.time()
    
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    
    print(f"Engine/Session setup: {time.time()-start_total:.4f}s")
    
    s = time.time()
    db = SessionLocal()
    print(f"Session creation: {time.time()-s:.4f}s")
    
    s = time.time()
    db.execute(text("SELECT 1"))
    print(f"SELECT 1: {time.time()-s:.4f}s")
    
    s = time.time()
    res = db.execute(text("SELECT COUNT(*) FROM processed_trades"))
    cnt = res.scalar()
    print(f"COUNT(*): {time.time()-s:.4f}s ({cnt} rows)")
    
    db.close()
    print(f"Total time: {time.time()-start_total:.4f}s")

if __name__ == "__main__":
    test_sqlalchemy_speed()
