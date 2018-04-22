import sqlite3


class Database:
    def __init__(self, path):
        self.__con = sqlite3.connect(path, check_same_thread=False)
        self.__con.row_factory = sqlite3.Row
        self.__cur = self.__con.cursor()

    def execute(self, sql):
        self.__cur.execute(sql)
        self.__con.commit()
        return self.__cur

    def __del__(self):
        self.__con.close()



# id | name  | tags  | allow_post_months     | allow_post_days       | when_last_used    | used_times
#    |       |       | NULL - all, '' - none | NULL - all, '' - none |                   | default 0

'''
cur.execute('INSERT INTO users (id, firstName, secondName) VALUES(NULL, "Guido", "van Rossum")')
con.commit()
print(cur.lastrowid)
cur.execute('SELECT * FROM users')
print(cur.fetchall())
'''

