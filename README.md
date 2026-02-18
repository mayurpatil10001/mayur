# 🏁 Trading Platform Project

## 📁 Project Structure

To maintain a clean working environment, the project is organized as follows:

### **核心文件夹 (Core Folders)**
- `trading_platform/`: Main backend application (FastAPI, Services, Routers).
- `frontend/`: React-based trade optimization dashboard.
- `docs/`: Technical documentation and integration summaries.

### **脚本与工具 (Scripts & Tools)**
- `scripts/`: Operational scripts for daily tasks (restarts, imports, database optimization).
- `tools/`: Diagnostic and auditing tools for deep-diving into trade data and logs.
- `tests/`: Comprehensive test suite and verification scripts.

### **数据与维护 (Data & Maintenance)**
- `data/samples/`: Historical `.txt` exports and sample datasets from Sierra Chart.
- `debug/`: Batch files, local HTML utilities, and temporary development databases.
- `legacy/`: Archive of retired script versions and outdated experimental code.
- `logs/archive/`: Historical execution logs and parsing traces.

### **根目录文件 (Root Files)**
- `main.py`: Entry point for the API server.
- `trading_platform.db`: Primary project database (SQLite).
- `app_settings.json`: Global application configuration.
- `import_config.yaml`: Configuration for binary scan paths.
- `requirements.txt`: Python dependency list.
- `Dockerfile` / `docker-compose.yml`: Containerization configuration.

---
*Last organized: February 18, 2026*
