import database


class Project:
    def __init__(self):
        self.__db_structure = database.Database('structure.db')

        # Initialize table with the list of projects
        sql_init_projects = """
            CREATE TABLE IF NOT EXISTS projects (
                id      INTEGER PRIMARY KEY ASC AUTOINCREMENT UNIQUE NOT NULL,
                name    VARCHAR(40) NOT NULL
            );
        """
        self.__db_structure.execute(sql_init_projects)

        sql_init_vk_groups = """
            CREATE TABLE IF NOT EXISTS vk_groups (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                application_id          VARCHAR(40) NOT NULL,
                application_secret_key  VARCHAR(200) NOT NULL,
                group_id                VARCHAR(40) NOT NULL,
                project_id              INTEGER
            );
        """
        self.__db_structure.execute(sql_init_vk_groups)

        sql_init_telegram_groups = """
            CREATE TABLE IF NOT EXISTS telegram_groups (
                id         INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                chat_id    VARCHAR(200),
                bot_token  VARCHAR(200),
                project_id INTEGER
            );
        """
        self.__db_structure.execute(sql_init_telegram_groups)

        # TODO: order by last record in logs DESC
        sql = """
            SELECT
                projects.name AS project_name,
                vk_groups.application_id as vk_application_id,
                vk_groups.application_secret_key,
                vk_groups.group_id as vk_group_id,
                telegram_groups.chat_id AS telegram_chat_id,
                telegram_groups.bot_token AS telegram_bot_token
            FROM
                projects
            INNER JOIN vk_groups
                ON projects.id = vk_groups.project_id
            LEFT JOIN telegram_groups
                ON projects.id = telegram_groups.project_id
        """
        cursor = self.__db_structure.execute(sql)
        q_projects = cursor.fetchall()
        self.projects = []
        self.project = None
        for row in q_projects:
            p = {}
            project_dict = dict(zip(row.keys(), row))
            for key, value in project_dict.items():
                p[key] = str(value).strip()
            self.projects.append(p)
        if len(self.projects):
            self.project = self.projects[0]

        # Creating the table if it doesn't exist
        self.__db = database.Database(self.get_project_path() + '/database.db')
        sql_init_images = """
            CREATE TABLE IF NOT EXISTS """+self.get_name()+""" (
                id                  INTEGER         PRIMARY KEY ASC AUTOINCREMENT UNIQUE NOT NULL,
                name                VARCHAR(200)    NOT NULL,
                tags                VARCHAR(200),
                allow_post_months   VARCHAR(100),
                allow_post_days     VARCHAR(200),
                except_post_months  VARCHAR(200),
                except_post_days    VARCHAR(200)
            );
        """
        self.__db.execute(sql_init_images)

        # Creating log table if it doesn't exist
        sql_init_log = """
            CREATE TABLE IF NOT EXISTS activity_log (
                id                  INTEGER PRIMARY KEY ASC AUTOINCREMENT UNIQUE NOT NULL,
                artwork_id          INTEGER,
                vk_post_id          INTEGER,
                telegram_post_id    INTEGER,
                message             VARCHAR(400),
                post_date           DATETIME DEFAULT (DateTime('now', 'localtime')) NOT NULL
            );
        """
        self.__db.execute(sql_init_log)


    def get_projects(self):
        return self.projects

    def get_project_list(self, key='project_name'):
        return list(project[key] for project in self.projects)

    def get_project(self):
        return self.project

    def set_project(self, project_name):
        for pr in self.projects:
            if pr['project_name'] == project_name:
                self.project = pr
                return True
        print("Project with name "+project_name+" does not exist")
        return False

    def get_name(self):
        return self.project['project_name']

    def get_project_path(self):
        return 'projects/' + self.get_name()

    def get_img_path_new(self):
        return self.get_project_path() + '/images_new'

    def get_img_path_working(self):
        return self.get_project_path() + '/images_working'

    def get_vk_application_id(self):
        return self.project['vk_application_id']

    def get_application_secret_key(self):
        return self.project['application_secret_key']

    def get_vk_group_id(self):
        return self.project['vk_group_id']

    def get_telegram_chat_id(self):
        return self.project['telegram_chat_id']

    def get_telegram_bot_token(self):
        return self.project['telegram_bot_token']
