import sqlite3

from singleton import singleton

@singleton
class WbData:

    def __init__(self, db_path: str="wb.sqlite"):
        self.db_path = db_path
        self.connected = False
        self.db = None

    def connect(self):
        if not self.connected:
            try:
                self.db = sqlite3.connect(self.db_path)
            except Exception as e:
                print("[-] connect sqlite3 %s error: " % self.db_path, str(e))
                return False
            else:
                self.connected = True
        return True

    
