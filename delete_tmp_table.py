import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('DROP TABLE IF EXISTS _alembic_tmp_expense')
c.execute('DROP TABLE IF EXISTS alembic_version')
conn.commit()
conn.close()
print("Temporary tables deleted.")