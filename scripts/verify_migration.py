import sys
import os
import asyncio
from sqlalchemy import create_engine, func, select, table, inspect

sys.path.append(os.getcwd())
from app.core.config import settings

DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
DB_NAME = settings.DB_NAME

def get_db_url(db_type: str):
    if db_type == "mysql":
        return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@db:3306/{DB_NAME}"
    elif db_type == "postgres":
        return f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@postgres:5432/{DB_NAME}"
    else:
        raise ValueError("Uknown DB type. Select 'mysql' or 'postgres'.")
    
def get_table_counts(engine):
    counts = {}
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    if "alembic_version" in table_names:
        table_names.remove("alembic_version")
        
    with engine.connect() as conn:
        for t_name in table_names:
            stmt = select(func.count()).select_from(table(t_name))
            count = conn.scalar(stmt)
            counts[t_name] = count
            
    return counts

def main():
    print("Verifying migration consistency...")
    print(f"Database: {DB_NAME}")
    
    print("Connecting to source: MySQL...")
    mysql_engine = create_engine(get_db_url("mysql"))
    try:
        mysql_data = get_table_counts(mysql_engine)
    except Exception as ex:
        print(f"Failed to read/connect MySQL: {ex}")
    finally:
        mysql_engine.dispose()
        
    print("Connecting to destination: PostgreSQL...")
    pg_engine = create_engine(get_db_url("postgres"))
    try:
        pg_data = get_table_counts(pg_engine)
    except Exception as ex:
        print(f"Failed to read/connect PostgreSQL: {ex}")
    finally:
        pg_engine.dispose()
        
    print("Consistiency results:")
    print("-" * 61)
    print(f"{'Table Name':<30} | {'MySQL':<8} | {'Postgres':<8} | {'Status'}")
    print("-" * 61)
    
    all_tables = set(mysql_data.keys()) | set(pg_data.keys())
    success = True
    
    for t in all_tables:
        m_count = mysql_data.get(t, "N/A")
        p_count = pg_data.get(t, "N/A")
        
        if m_count == p_count:
            status = "OK"
        else:
            status = "FAIL"
            success = False
        
        print(f"{t:<30} | {str(m_count):<8} | {str(p_count):<8} | {status}")
        
    print("-" * 61)
    
    if success:
        print("\nSUCCESS. Data migration verified successfully.")
    else:
        print("\nFAILED. Rows count do not match.")
        
if __name__ == "__main__":
    main()