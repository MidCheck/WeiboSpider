from pathlib import Path
from contextlib import contextmanager
from singleton import singleton
import sqlite3

@contextmanager
def open_cursor(conn: sqlite3.Connection):
    cursor = conn.cursor()
    try:
        yield cursor
    except Exception as e:
        cursor.close()
        raise e
    else:
        cursor.close()

@singleton
class WbData:

    def __init__(self, user_path: str="user.db", wb_path: str="wb.db"):
        self.user_path = user_path
        self.wb_path = wb_path
        self.connected = False
        self.user_db = None
        self.wb_db = None
        self.user_created = Path(user_path).exists()
        self.wb_created = Path(wb_path).exists()
        self.connect()

    def close(self):
        if self.connected:
            self.wb_db.close()
            self.user_db.close()
            self.connected = False

    def connect(self):
        if not self.connected:
            try:
                self.wb_db = sqlite3.connect(self.wb_path)
                self.user_db = sqlite3.connect(self.user_path)
            except Exception as e:
                print("[-] connect sqlite3 error: ", str(e))
                return False
            else:
                self.connected = True
                if not self.user_created:
                    self.create_user_table()
                if not self.wb_created:
                    self.create_wbmsg_table()
        return True

    def create_user_table(self):
        sql = "CREATE TABLE user(uid char(10) PRIMARY KEY NOT NULL, nick varchar(300), avator varchar(300));"
        with open_cursor(self.user_db) as cursor:
            cursor.execute(sql)
            self.user_db.commit()
    
    def create_wbmsg_table(self):
        msg_sql = "CREATE TABLE message(\
            mid char(16) PRIMARY KEY NOT NULL, uid char(10) NOT NULL, top varchar(100), \
                client varchar(128), time date NOT NULL, content text);"
        comment_sql = "CREATE TABLE comment(mid char(16) NOT NULL, uid char(10) NOT NULL, \
                time date, content text);"
        with open_cursor(self.wb_db) as cursor:
            cursor.execute(msg_sql)
            cursor.execute(comment_sql)
            self.wb_db.commit()
    
    def insert_users(self, users: list):
        sql = 'INSERT or IGNORE INTO user values(?, ?, ?);'
        with open_cursor(self.user_db) as cursor:
            for uid, nick_name, avator in users:
                cursor.execute(sql, (uid, nick_name, avator))
            self.user_db.commit()

    def insert_messages(self, messages: list):
        sql = 'INSERT or IGNORE INTO message values(?, ?, ?, ?, ?, ?);'
        with open_cursor(self.wb_db) as cursor:
            for mid, uid, top, sfrom, stime, content in messages:
                cursor.execute(sql, (mid, uid, top, sfrom, stime, content))
            self.wb_db.commit()
    
    def insert_comments(self, comments: list):
        sql = 'INSERT or IGNORE INTO comment values(?, ?, ?, ?);'
        with open_cursor(self.wb_db) as cursor:
            for mid, uid, stime, content in comments:
                cursor.execute(sql, (mid, uid, stime, content))
            self.wb_db.commit()

    def select_wb_tables(self, sql):
        with open_cursor(self.wb_db) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def select_contents(self):
        sql1 = 'SELECT content FROM message;'
        sql2 = 'SELECT content FROM comment;'
        contents = self.select_wb_tables(sql1)
        contents += self.select_wb_tables(sql2)
        return [ content[0] for content in contents ]
