import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        """Open a fresh connection to MySQL."""
        try:
            self.conn = mysql.connector.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', 'Abdshyam17*'),
                database=os.getenv('DB_NAME', 'ai_receptionist')
            )
            self.cursor = self.conn.cursor(dictionary=True)
            print("✅ Database connected successfully!")
        except Error as e:
            print(f"❌ Error connecting to database: {e}")
            self.conn = None
            self.cursor = None

    def _ensure_connection(self):
        """Make sure we have a live connection before running a query.
        MySQL silently drops idle connections after a timeout, which is
        what causes 'Lost connection to MySQL server during query' -
        this transparently reconnects instead of failing."""
        try:
            if self.conn is None or not self.conn.is_connected():
                print("⚠️ Database connection lost - reconnecting...")
                self._connect()
            else:
                # Cheap keepalive check; auto-reconnects if the server dropped us
                self.conn.ping(reconnect=True, attempts=3, delay=2)
                self.cursor = self.conn.cursor(dictionary=True)
        except Error as e:
            print(f"❌ Reconnect attempt failed: {e}")
            self._connect()

    def execute_query(self, query, params=None):
        """Execute SELECT query"""
        self._ensure_connection()
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ Query error: {e}")
            return None

    def insert_data(self, query, params):
        """Insert data into database"""
        self._ensure_connection()
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            print(f"✅ Data inserted successfully! ID: {self.cursor.lastrowid}")
            return self.cursor.lastrowid
        except Error as e:
            print(f"❌ Insert error: {e}")
            self.conn.rollback()
            return None

    def update_data(self, query, params):
        """Update database records"""
        self._ensure_connection()
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            print("✅ Data updated successfully!")
            return True
        except Error as e:
            print(f"❌ Update error: {e}")
            self.conn.rollback()
            return False

    def close(self):
        if self.conn and self.conn.is_connected():
            self.cursor.close()
            self.conn.close()
            print("✅ Database connection closed")

# Initialize database
db = Database()