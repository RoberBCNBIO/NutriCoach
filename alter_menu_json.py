import os
import psycopg2

db_url = os.getenv("DATABASE_URL")

def alter_column():
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
        ALTER TABLE menulogs
        ALTER COLUMN menu_json TYPE JSONB
        USING menu_json::jsonb;
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Columna 'menu_json' convertida a JSONB correctamente.")
    except Exception as e:
        print("❌ Error ejecutando ALTER TABLE:", e)

if __name__ == "__main__":
    alter_column()
