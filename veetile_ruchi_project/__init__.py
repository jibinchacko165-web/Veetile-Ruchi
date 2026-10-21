# PostgreSQL is the active database engine for Veetile-Ruchi.
# PyMySQL fallback is conditionally maintained only if a legacy MySQL engine is explicitly configured.
import os

if os.getenv('DB_ENGINE', '').endswith('mysql'):
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

