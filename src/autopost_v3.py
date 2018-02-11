# -*- coding: utf-8 -*-
import base64
import io
import pickle
import webbrowser
from urllib.parse import parse_qs
from datetime import datetime, timedelta
import vk
import time
import requests
import json
from time import sleep
import file_control
import database
import string
import random

class Autopost:
    # file, where auth data is saved
    __AUTH_FILE = 'assets/.auth_data'
    # chars to exclude from filename
    __FORBIDDEN_CHARS = '/\\\?%*:|"<>!'

    # "__" means that attribute is private
    __group_id = 0
    __project_name = ''
    __app_id = ''

    def __init__(self, application_id, application_secret_key, gid, pname):
        self.__project_name = pname

        self.__project_root_path = 'projects/'+pname
        self.__img_folder_path_new = self.__project_root_path + '/images_new'
        self.__img_folder_path_working = self.__project_root_path + '/images_working'

        # Create folder structure
        print("Checking folder structure...")
        if file_control.create_folder(self.__img_folder_path_new):
            print("Directory created: '" + self.__img_folder_path_new + "'")
        if file_control.create_folder(self.__img_folder_path_working):
            print("Directory created: '" + self.__img_folder_path_working + "'")
        print("Folder structure checked.\n")

        self.__db = database.Database(self.__project_root_path+'/database.db')
        # Creating the table if it doesn't exist
        sqlInitImages = "CREATE TABLE IF NOT EXISTS "+pname+" (" \
                  "    id                 INTEGER       PRIMARY KEY ASC AUTOINCREMENT" \
                  "                                     UNIQUE" \
                  "                                     NOT NULL," \
                  "    name               VARCHAR (200) NOT NULL," \
                  "    tags               VARCHAR (200)," \
                  "    allow_post_months  VARCHAR (100)," \
                  "    allow_post_days    VARCHAR (200)," \
                  "    except_post_months VARCHAR (200)," \
                  "    except_post_days   VARCHAR (200)" \
                  ");"
        self.__db.execute(sqlInitImages)
        # Creating log table if it doesn't exist
        sqlInitLog = "CREATE TABLE IF NOT EXISTS activity_log (" \
                  "    id                 INTEGER       PRIMARY KEY ASC AUTOINCREMENT" \
                  "                                     UNIQUE" \
                  "                                     NOT NULL," \
                  "    artwork_id         INTEGER," \
                  "    vk_post_id         INTEGER," \
                  "    telegram_post_id   INTEGER," \
                  "    message            VARCHAR(400)," \
                  "    post_date          DATETIME      DEFAULT (DateTime('now', 'localtime'))" \
                  "                                     NOT NULL" \
                  ");"
        self.__db.execute(sqlInitLog)

        self.refresh_image_queue()

        self.__app_id = application_id
        self.__app_secret_key = application_secret_key
        self.__group_id = gid
        self.__access_token, _ = self.get_auth_params()
        self.__api = self.get_api(self.__access_token)
        #self.__watermarker = watermarker.Watermarker('assets/watermark_'+pname+'.png', pname + '/notWatermarkedArchive/')


    def get_post_difference(self):
        sql = "SELECT COUNT(vk_post_id) AS vk_post_count, COUNT(telegram_post_id) AS telegram_post_count FROM activity_log"
        cursor = self.__db.execute(sql)
        result = cursor.fetchone()
        return {'vk_post_count': result['vk_post_count'], 'telegram_post_count': result['telegram_post_count']}


    def get_group_id(self):
        return self.__group_id

    def get_group_info_by_id(self, id):
        method_url = 'https://api.vk.com/method/groups.getById?'
        data = dict(group_id=id) #It is possible to get private info, if passing other params. See documentation
        response = requests.post(method_url, data)
        result = json.loads(response.text)
        return result['response']

    def get_group_avatar(self):
        avatar_url = self.get_group_info_by_id(
            self.get_group_id()
        )[0]['photo_big']
        avatar_path = self.__project_root_path+'/avatar.jpg'
        f = open(avatar_path, 'wb')
        f.write(requests.get(avatar_url).content)
        f.close()
        return avatar_path

    def refresh_image_queue(self):
        # Refreshing all old images
        self.refresh_old_images()
        # Refreshing new images
        self.refresh_new_images()
        # Clean up database(delete all rows, that refer to images, which don't exist in working folder)
        self.db_cleanup()


    def refresh_old_images(self):
        old_images_list = file_control.get_image_list(self.__img_folder_path_working)
        ids_updated = []
        for old_image in old_images_list:
            image = self.parse_image_name(old_image)
            image_name = image['name'] + '.' + image['extension']
            image_tags_string = ",".join(image['tags'])
            # Checking if image exists in DB
            sql = "SELECT id FROM " + self.__project_name + " WHERE name = '" + image_name + "'"
            cursor = self.__db.execute(sql)
            result = cursor.fetchone()
            if result is None:
                sql = "INSERT INTO " + self.__project_name + "(name,tags) VALUES ('" + image_name + "','" + image_tags_string + "')"
                cursor = self.__db.execute(sql)
                print("Row inserted in DB: id=" + str(cursor.lastrowid))
            else:
                # Checking if tags are updated
                sql = "SELECT id FROM " + self.__project_name + " WHERE name = '" + image_name + "' AND tags='" + image_tags_string + "'"
                cursor = self.__db.execute(sql)
                if len(cursor.fetchall()) == 0:
                    row_id = result['id']
                    sql = "UPDATE " + self.__project_name + " SET tags='" + image_tags_string + "' WHERE name='"+image_name+"'"
                    self.__db.execute(sql)
                    ids_updated.append(row_id)
        if len(ids_updated):
            ids_updated.sort()
            for row_id in ids_updated:
                print("Row updated in DB: id=" + str(row_id))


    def refresh_new_images(self):
        new_images_list = file_control.get_image_list(self.__img_folder_path_new)
        for new_image in new_images_list:
            image = self.parse_image_name(new_image)
            if not self.is_valid_name(name=image['name'],size=4) or not self.image_exists_in_db(name=image['name']):
                image['name'] = self.generate_image_name(size=4)
            image_tags_string = ",".join(image['tags'])
            db_image_name = image['name'] + '.' + image['extension']
            disk_image_name = image['name'] + ("," + image_tags_string if image_tags_string.strip()!='' else '') + '.' + image['extension']
            file_control.rename_img(self.__img_folder_path_new, new_image, disk_image_name)
            sql = "INSERT INTO " + self.__project_name + "(name,tags) VALUES ('" + db_image_name + "','" + image_tags_string + "')"
            cursor = self.__db.execute(sql)
            print("Row inserted in DB: id=" + str(cursor.lastrowid))
            file_control.move_img(self.__img_folder_path_new, self.__img_folder_path_working, disk_image_name)


    def db_cleanup(self):
        working_images_list = file_control.get_image_list(self.__img_folder_path_working)
        working_images_list_sql_string = ''
        is_first = True
        for working_image in working_images_list:
            image = self.parse_image_name(working_image)
            image_name = image['name'] + "." + image['extension']
            if is_first == False:
                working_images_list_sql_string += ",'" + image_name + "'"
            else:
                working_images_list_sql_string += "'" + image_name + "'"
                is_first = False
        sql = "DELETE FROM " + self.__project_name + " WHERE name NOT IN(" + working_images_list_sql_string + ")"
        cursor = self.__db.execute(sql)
        if cursor.rowcount:
            print("Database cleaned. Rows deleted: " + str(cursor.rowcount))


    # Returns dictionary{'name', 'tags', 'extension'}
    def parse_image_name(self, image_full_name):
        image_name_with_tags = image_full_name.split('.')[0]
        image_name = image_name_with_tags.split(',')[0]
        image_extension = image_full_name.split('.')[-1]  # Last element of "split()" result
        image_tags = image_name_with_tags.split(',')
        del image_tags[0]
        return {'name': image_name, 'tags': image_tags, 'extension': image_extension}

    def image_exists_in_db(self, name):
        sql = "SELECT id FROM " + self.__project_name + " WHERE name = '" + name + "'"
        cursor = self.__db.execute(sql)
        result = cursor.fetchone()
        if result is None:
            return False
        return True

    def is_valid_name(self, name, size):
        if len(name) != size:
            return False
        for i in name:
            if not i.isalnum() or not i.isupper():
                return False
        return True

    def generate_image_name(self,size):
        while True:
            random_value = self.generate_alphanumeric(size)
            sql = "SELECT id FROM "+self.__project_name+" WHERE name LIKE '"+random_value+"%'"
            cursor = self.__db.execute(sql)
            recordCount = len(cursor.fetchall())
            if recordCount == 0:
                return random_value

    def generate_alphanumeric(self, size, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))


    def get_auth_params(self):
        access_token = None
        user_id = None
        # Trying to open saved params firstly
        try:
            with open(self.__AUTH_FILE, 'rb') as pkl_file:
                token = pickle.load(pkl_file)
                expires = pickle.load(pkl_file)
                uid = pickle.load(pkl_file)
                #############################################
                # remove this if using the instructions below
                access_token = token
                user_id = uid
                #############################################
            # The instructions below are deprecated. Just recreate access_token every time the problem appears
            '''
            if datetime.now() < expires:
                access_token = token
                user_id = uid
            '''
        except IOError:
            pass

        # If no saved params found, getting new ones
        if not access_token or not user_id:
            auth_url = ("https://oauth.vk.com/authorize?client_id={app_id}"
                        "&redirect_uri=https://oauth.vk.com/blank.html"
                        "&scope=notify,friends,photos,audio,video,docs,notes,pages,status,offers,questions,wall,groups,messages,notifications,stats,ads,offline"
                        "&client_secret={app_secret_key}"
                        "&display=popup&response_type=token&v=5.60".format(app_id=self.__app_id,app_app_secret_key=self.__app_secret_key))
            webbrowser.open_new_tab(auth_url)
            redirected_url = input("Paste here url you were redirected:\n")
            aup = parse_qs(redirected_url)
            aup['access_token'] = aup.pop(
                'https://oauth.vk.com/blank.html#access_token')
            access_token = aup['access_token'][0]
            user_id = aup['user_id'][0]
            expires_in = aup['expires_in'][0]
            expires_date = datetime.now() + timedelta(seconds=int(expires_in))
            # Saving auth params in file
            with open(self.__AUTH_FILE, 'wb') as output:
                pickle.dump(access_token, output)
                pickle.dump(expires_date, output)
                pickle.dump(user_id, output)

        return access_token, user_id

    def get_api(self, access_token):
        session = vk.Session(access_token=access_token)
        return vk.API(session)


    def get_auto_planned_posts(self):
        response = []

        sql = "SELECT artwork_id, vk_post_id, post_date FROM activity_log WHERE post_date > DateTime('now', 'localtime') AND vk_post_id IS NOT NULL"
        result = self.__db.execute(sql).fetchall()
        if len(result):
            for post in result:
                response.append(
                    {
                        'artwork_id': post['artwork_id'],
                        'vk_post_id': post['vk_post_id'],
                        'post_date': post['post_date']
                    }
                )
        return response



    def get_posts(self, filter = "all", offset=0):
        owner_id = str(-int(self.__group_id))
        domain = "public" + self.__group_id
        v = 5.58
        if offset == (-1): # Offset should be positive
            offset = 0
        return self.__api.wall.get(owner_id=owner_id, domain=domain, filter=filter, extended=1, offset=offset, v=v)


    def get_upload_image_link(self, img):
        method_url = 'https://api.vk.com/method/photos.getWallUploadServer?'
        data = dict(access_token=self.__access_token, gid=self.__group_id)
        response = requests.post(method_url, data)
        result = json.loads(response.text)
        upload_url = result['response']['upload_url']
        return upload_url


    def upload_image(self, upload_url, img):
        response = requests.post(upload_url, files=img)
        result = json.loads(response.text)
        return result


    def save_image_on_server(self, result):
        method_url = 'https://api.vk.com/method/photos.saveWallPhoto?'
        data = dict(access_token=self.__access_token, gid=self.__group_id, photo=result['photo'], hash=result['hash'],
                    server=result['server'])
        response = requests.post(method_url, data)
        result = json.loads(response.text)['response'][0]['id']
        return result


    def generate_tags_string(self, image_tags=[]):
        suffix_tags = ''
        if len(image_tags):
            tag1 = random.choice(image_tags)
            suffix_tags = '#' + tag1
            image_tags.remove(tag1)
            if len(image_tags):
                tag2 = random.choice(image_tags)
                suffix_tags += ' #' + tag2
        return ('#' + self.__project_name + ' ' + suffix_tags).strip()


    def get_datetime_starting_point(self):
        total_posts_planned = self.get_posts(filter="postponed")["count"]
        if total_posts_planned > 0:
            print("Posts already planned: "+str(total_posts_planned))
        response = self.get_posts(filter="postponed", offset=total_posts_planned-1)
        if response['count']:  # If there are planned posts, use next day after the last planned date
            last_post = response['items'][len(response['items']) - 1]
            last_post_datetime = datetime.fromtimestamp(last_post['date'])
        else:  # Else - use tomorrow's date
            last_post_datetime = datetime.now()
        starting_point = last_post_datetime + timedelta(days=1) # Next day from last planned post
        starting_point = starting_point.replace(
            hour=9,
            minute=random.randint(1, 59),
            microsecond=0
        )
        return starting_point


    def create_post_schedule(self, days_number=0, perDay=0):
        schedule = []
        # Creating temporary table. Move all logs into it and process the table in loop to avoid incorrect choices
        self.__db.execute("CREATE TEMP TABLE activity_log_temp AS SELECT * FROM activity_log")
        total_starting_point = self.get_datetime_starting_point()
        for x in range(days_number):
            daily_starting_point = total_starting_point + timedelta(days=x)  # Starting datetime point
            minutes_diff_distribution = self.distribution(1,600,perDay) # numbers in minutes, relatively to starting point
            for minuteAdd in minutes_diff_distribution:
                datetime_to_post = daily_starting_point + timedelta(minutes=minuteAdd+random.randint(1, 20))
                datetime_to_post_string = datetime_to_post.strftime("%Y-%m-%d %H:%M:%S")
                datetime_to_post_unix = int(time.mktime(time.strptime(datetime_to_post_string, '%Y-%m-%d %H:%M:%S')))
                image = self.choose_image(datetime_to_post, 'activity_log_temp')
                if image: # If image has been chosen succesfully
                    self.__db.execute(
                        "INSERT INTO activity_log_temp(artwork_id, post_date) "
                        "VALUES(" + str(image['id']) + ", '" + datetime_to_post_string + "')"
                    )
                    schedule.append(
                        {
                            'image': image,
                            'datetime': datetime_to_post,
                            'datetime_string': datetime_to_post_string,
                            'datetime_unix': datetime_to_post_unix
                        }
                    )
        self.__db.execute("DROP TABLE activity_log_temp")
        return schedule


    def choose_image(self, timestamp=datetime.now(), activity_log_table='activity_log'):
        #the_datetime = datetime.fromtimestamp(timestamp)
        the_datetime = timestamp
        day = the_datetime.day
        month = the_datetime.month
        # Variable 'limit' is the randomisation range
        # IMPORTANT - the value should be much less then total number of records in selection
        limit = 3
        sql = "SELECT * FROM (" \
                "SELECT " \
                    ""+self.__project_name+".id, " \
                    ""+self.__project_name+".name, " \
                    ""+self.__project_name+".tags, " \
                    ""+self.__project_name+".allow_post_days, " \
                    "" + self.__project_name + ".allow_post_months, " \
                    "" + self.__project_name + ".except_post_days, " \
                    "" + self.__project_name + ".except_post_months, " \
                    "ifnull(al.used_times,0), " \
                    "al.when_last_used " \
                    "FROM "+self.__project_name+" " \
                "LEFT JOIN (" \
                    "SELECT " \
                    "artwork_id, " \
                    "count(*) AS used_times, " \
                    "MAX(post_date) AS when_last_used " \
                    "FROM "+activity_log_table+" " \
                    "GROUP BY artwork_id" \
                ") al " \
                "ON "+self.__project_name+".id = al.artwork_id " \
                "WHERE ((',' || allow_post_days || ',') LIKE '%,"+str(day)+",%' OR allow_post_days IS NULL) " \
                "AND ((',' || allow_post_months || ',') LIKE '%,"+str(month)+",%' OR allow_post_months IS NULL) " \
                "AND ((',' || except_post_days || ',') NOT LIKE '%," + str(day) + ",%' OR except_post_days IS NULL) " \
                "AND ((',' || except_post_months || ',') NOT LIKE '%,"+str(month)+",%' OR except_post_months IS NULL) " \
                "ORDER BY al.used_times, date(al.when_last_used) LIMIT "+str(limit)+" " \
              ") ORDER BY RANDOM() LIMIT 1"
        result = self.__db.execute(sql).fetchone()
        if result:
            image = {
                'id': result['id'],
                'name': result['name'].split('.')[0],
                'tags': self.generate_tags_string(result['tags'].split(',') if result['tags'].strip()!='' else []),
                'extension': result['name'].split('.')[-1],
                'image_path': self.__img_folder_path_working + '/' + result['name'].split('.')[0] + (',' + result['tags'] if result['tags'].strip()!='' else '') + '.' + result['name'].split('.')[1]
            }
            return image
        else:
            return False

    def isEnglish(self,s):
        try:
            s.encode(encoding='utf-8').decode('ascii')
        except UnicodeDecodeError:
            return False
        else:
            return True

    def delete_all_planned_posts(self):  # Deleting all planned posts, based on post_id from DB
        response = {}

        sql = "SELECT vk_post_id, post_date FROM activity_log WHERE post_date > DateTime('now', 'localtime') AND vk_post_id IS NOT NULL"
        result = self.__db.execute(sql).fetchall()
        for post in result:
            sleep(0.4)  # Time in seconds. Max: 3/sec
            if str(post['vk_post_id']).strip() != 0:
                if self.delete_posts(post_id=post['vk_post_id']):
                    response['status'] = 1
                    response['message'] = "VK post " + str(post['vk_post_id']) + " deleted"
                    sql = "DELETE FROM activity_log WHERE vk_post_id = "+str(post['vk_post_id'])
                    cursor = self.__db.execute(sql)

                    sql = "SELECT post_date FROM activity_log WHERE post_date > DateTime('now', 'localtime') AND vk_post_id IS NOT NULL ORDER BY id DESC LIMIT 1"
                    result = self.__db.execute(sql).fetchone()
                    if result:
                        response['post_date'] = str(result['post_date'])
                else:
                    response['status'] = 0
                    response['message'] = "Error deleting post "+str(post['vk_post_id'])
                with open(self.__project_root_path + '/' + self.__project_name + '_log.txt', 'a') as logfile:
                    logfile.write(str(response['message']) + '\n')
            yield response

    def delete_posts(self, post_id = 0, filter = "postponed"):
        owner_id = str(-int(self.__group_id))
        if post_id:
            self.__api.wall.delete(owner_id=owner_id, post_id=post_id)
            return True
        # if post_id = 0, deleting all posts, according to the filter
        else:
            number_of_posts_to_be_deleted = self.get_posts(filter)["count"]
            #print(str(number_of_posts_to_be_deleted) + " posts are going to be deleted")
            while len(self.get_posts(filter)["items"]) > 0: #Looping until all posts deleted, because maximum is 20 posts
                posts = self.get_posts(filter)["items"]
                for post in posts:
                    sleep(0.4)  # Time in seconds. Max: 3/sec
                    response = self.__api.wall.delete(owner_id=owner_id, post_id=post["id"])
                    if response == 1:
                        print("post "+str(post["id"])+" deleted")
                        return True


    # Get certain number of values values, distributed within given range
    # returns [a1, a2, a3, a4, ... , an]
    def distribution(self, start, end, n):
        if n < 1:
            raise Exception("behaviour not defined for n<1")
        if n == 1:
            return [end]
        step = (end - start) / float(n - 1)
        return [int(round(start + x * step)) for x in range(n)]

    def create_data_activity_log(self, insert=None):
        if insert:
            columns = []
            values = []
            if 'artwork_id' in insert and insert['artwork_id']:
                columns.append("artwork_id")
                values.append(insert['artwork_id'])
            if 'vk_post_id' in insert:
                columns.append("vk_post_id")
                values.append(insert['vk_post_id'])
            if 'telegram_post_id' in insert:
                columns.append("telegram_post_id")
                values.append(insert['telegram_post_id'])
            if 'message' in insert:
                columns.append("message")
                values.append("'"+insert['message']+"'")
            if 'post_date' in insert:
                columns.append("post_date")
                values.append("'"+insert['post_date']+"'")
            if len(columns) and len(values) and len(columns)==len(values):
                sql = "INSERT INTO activity_log("+','.join(columns)+")"
                sql += "VALUES("+','.join(values)+")"
                self.__db.execute(sql)
            with open(self.__project_root_path + '/' + self.__project_name + '_log.txt', 'a') as logfile:
                logfile.write(json.dumps(insert) + '\n')
        return True


    def add_posts(self, scheduled=None, instant=None):
        planned_posts = []
        activity_log_args = {}

        is_scheduled = 0
        is_instant = 0

        if scheduled is not None and type(scheduled) is dict: #Scheduled
            print("scheduled")
            is_scheduled = 1
            if 'days_number' in scheduled and 'per_day' in scheduled and scheduled['per_day'] > 0 and scheduled['days_number'] > 0:
                planned_posts = self.create_post_schedule(scheduled['days_number'], scheduled['per_day'])
                for index,post in enumerate(planned_posts):
                    post['telegram_args'] = {}
                    if index == 0: #The first one should be posted in Telegram
                        post['telegram_args']['image_path'] = post['image']['image_path']
                        post['telegram_args']['url'] = 'https://vk.com/public' + self.__group_id
                    post['vk_args'] = {}
                    post['vk_args']['owner_id'] = str(-int(self.__group_id))
                    post['vk_args']['signed'] = 1
                    post['vk_args']['message'] = post['image']['tags']
                    post['vk_args']['publish_date'] = post['datetime_unix']
        elif (instant is not None) and (type(instant) is dict): #Instant
            is_instant = 1
            post = {}

            post['vk_args'] = {}
            post['telegram_args'] = {}

            if 'auto_image' in instant and instant['auto_image'] == 1:
                post['image'] = self.choose_image()

            attachment_images = []
            vk_attachments = [] #Used for suggested posts

            if 'vk' in instant and instant['vk'] == 1:
                vk_message = ''
                if 'auto_image' in instant and instant['auto_image'] == 1:
                    if 'auto_tags' in instant and instant['auto_tags'] == 1 and post['image']:
                        vk_message = post['image']['tags']
                elif 'post_suggested' in instant and instant['post_suggested'] == 1:  # use suggested post
                    suggested_posts = self.get_posts(filter="suggests")['items']
                    for suggested_post in suggested_posts:
                        # print(json.dumps(suggested_post, indent=2))
                        # return
                        if 'attachments' in suggested_post:
                            activity_log_args['artwork_id'] = []
                            #print(json.dumps(suggested_post['attachments'], indent=2))
                            for attachment in suggested_post['attachments']:
                                if 'link' in attachment:
                                    attachment_type = str(attachment['type'])
                                    url = attachment[attachment_type]['url']
                                    vk_attachments.append(url)
                                if 'photo' in attachment: # filing local database with new artworks
                                    # getting the biggest resolution available
                                    biggest_res = 0
                                    for key in attachment['photo']:
                                        key_splitted = str(key).split('_')
                                        if key_splitted[0] == 'photo' and int(key_splitted[1]) > biggest_res:
                                            image_url = attachment['photo'][key]
                                            biggest_res = int(key_splitted[1])
                                    attachment_images.append(image_url)
                                    image_name = self.generate_image_name(size=4) + '.jpg'
                                    image_path = self.__img_folder_path_working + '/' + image_name
                                    f = open(image_path, 'wb')
                                    f.write(requests.get(image_url).content)
                                    f.close()
                                    sql = "INSERT INTO " + self.__project_name + "(name,tags) VALUES ('" + image_name + "','')"
                                    cursor = self.__db.execute(sql)
                                    print("Row inserted in DB: id=" + str(cursor.lastrowid))
                                    activity_log_args['artwork_id'].append(str(cursor.lastrowid))

                                    # <type><owner_id>_<media_id>,<type><owner_id>_<media_id>
                                    attachment_type = str(attachment['type'])
                                    owner_id = str(attachment[attachment_type]['owner_id'])
                                    media_id = str(attachment[attachment_type]['id'])
                                    vk_attachments.append(
                                        attachment_type + owner_id + '_' + media_id
                                    )
                                # suggested videos should also be posted in Telegram
                                if 'video' in attachment:
                                    attachment_type = str(attachment['type'])
                                    owner_id = str(attachment[attachment_type]['owner_id'])
                                    media_id = str(attachment[attachment_type]['id'])
                                    vk_attachments.append(
                                        attachment_type + owner_id + '_' + media_id
                                    )
                                    video = self.__api.video.get(
                                        owner_id=-int(self.__group_id),
                                        videos=str(attachment['video']['owner_id'])+'_'+str(attachment['video']['id'])+'_'+str(attachment['video']['access_key']),
                                        v=5.58
                                    )
                                    suggested_post['text'] = video['items'][0]['player'] #The first video(if many) is enough
                        post['vk_args']['attachments'] = ','.join(vk_attachments)
                        post['vk_args']['post_id'] = suggested_post['id']
                        activity_log_args['message'] = suggested_post['text']
                        if 'telegram' in instant and instant['telegram'] == 1:
                            post['telegram_args']['text'] = suggested_post['text']
                        break  # we need only one suggested post
                    # print(json.dumps(post['vk_args']['attachments'], indent=2))
                    # return
                if 'vk_tags' in instant and instant['vk_tags'] != '':
                    vk_message = instant['vk_tags']
                if 'message' in instant and instant['message'].strip() != '':
                    activity_log_args['message'] = instant['message']
                    vk_message = instant['message'] if vk_message.strip() == '' else vk_message+'\n'+instant['message']
                if vk_message.strip() != '':
                    post['vk_args']['message'] = vk_message
                if post['vk_args']: #If there is something to post
                    post['vk_args']['owner_id'] = str(-int(self.__group_id))
                    post['vk_args']['signed'] = 1
            if 'telegram' in instant and instant['telegram'] == 1:
                if 'auto_image' in instant and instant['auto_image'] == 1 and post['image']:
                    post['telegram_args']['image_path'] = post['image']['image_path']
                elif 'post_suggested' in instant and instant['post_suggested'] == 1:  # use suggested post
                    if len(attachment_images):
                        post['telegram_args']['image_urls'] = attachment_images
                if 'message' in instant and instant['message'].strip() != '':
                    activity_log_args['message'] = instant['message']
                    post['telegram_args']['text'] = instant['message']
                if 'with_vk_link' in instant and instant['with_vk_link'] == 1:
                    post['telegram_args']['url'] = 'https://vk.com/public'+self.__group_id
            planned_posts = [post]

        for post_index, post in enumerate(planned_posts):
            if 'image' in post and post['image'] != '':
                if post['image'] == False:
                    print("No applicable images found in database")
                    continue
                else:
                    activity_log_args['artwork_id'] = [str(post['image']['id'])]
                    try:
                        if post['image']['extension'].find('.gif') == -1:
                            if not self.isEnglish(post['image']['image_path']):
                                image_temp_name = "temp." + post['image']['extension']
                                file_control.copy_img1(
                                    img_path_old=post['image']['image_path'],
                                    img_path_new=self.__img_folder_path_working + '/' + image_temp_name
                                )
                                img_path = self.__img_folder_path_working + '/' + image_temp_name
                            else:
                                img_path = post['image']['image_path']
                            if post['vk_args']:
                                with open(img_path, 'rb') as file:
                                    img = {'photo': (img_path, file)}
                                    # Получаем ссылку для загрузки изображений
                                    upload_url = self.get_upload_image_link(img)
                                    # Загружаем изображение на url
                                    result = self.upload_image(upload_url, img)
                                    # Сохраняем фото на сервере и получаем id
                                    result = self.save_image_on_server(result)
                                    post['vk_args']['attachment'] = result
                            if post['telegram_args']:
                                post['telegram_args']['image_path'] = img_path
                        else:
                            print("'gif' file can't be uploaded\n")
                            continue
                    except Exception as e:
                        print('*'+str(e)+'*')
                        continue

            return_data = {}
            if post['vk_args']:
                post_id = (self.__api.wall.post(**post['vk_args']))['post_id']  # post_id
                activity_log_args['vk_post_id'] = str(post_id)
                if post['telegram_args'] and (is_instant and 'with_vk_link' in instant and instant['with_vk_link'] == 1): #Is customized instant
                    post['telegram_args']['url'] = 'https://vk.com/public'+self.__group_id+'?w=wall-'+self.__group_id+'_'+str(post_id)
                if 'image' in post:
                    return_data = post['image']
                if 'datetime_string' in post:
                    return_data['datetime_string'] = post['datetime_string']
                    activity_log_args['post_date'] = post['datetime_string']
                return_data['post_id'] = post_id
                return_data['status'] = 1
            if post['telegram_args']:
                telegram_post_id = self.telegram_post(**post['telegram_args'])
                return_data['status'] = 1
                if telegram_post_id:
                    return_data['telegram_post_id'] = str(telegram_post_id)
                    activity_log_args['telegram_post_id'] = str(telegram_post_id)
            elif 'telegram_post_id' in activity_log_args and post_index > 0: # Only first scheduled post is with Telegram
                del activity_log_args['telegram_post_id']

            # Creating log
            if activity_log_args:
                #print(activity_log_args)
                if 'artwork_id' in activity_log_args and len(activity_log_args['artwork_id']):
                    for index, artwork_id in enumerate(activity_log_args['artwork_id']): #if multiple artworks were uploaded
                        #if index > 0 and 'telegram_post_id' in activity_log_args: # Telegram post is being created only once in the loop
                            #del activity_log_args['telegram_post_id']
                        activity_log_args['artwork_id'] = artwork_id
                        self.create_data_activity_log(activity_log_args)
                else:
                    self.create_data_activity_log(activity_log_args)

            if 'image' in post and post['image'] != '':
                if not self.isEnglish(post['image']['image_path']):
                    file_control.delete_file(self.__img_folder_path_working + '/' + "temp." + post['image']['extension'])

            yield return_data


    def telegram_post(self, text='', image_path='', image_urls=[], url=''):
        '''
        image_urls = [
            "https://pp.userapi.com/c841232/v841232079/5dbf3/QURUaN9s-g4.jpg",
            "https://pp.userapi.com/c824601/v824601079/6dc9b/PiAAxX3jJeU.jpg"
        ]
        text = "\u0412\u0430\u0440\u0438\u0430\u0446\u0438\u0438 \u0432\u044b\u0436\u0438\u0432\u0448\u0438\u0445-\u0437\u0430\u0440\u0430\u0436\u0451\u043d\u043d\u044b\u0445\n\u0410\u0432\u0442\u043e\u0440 1-\u0433\u043e : https://youlootamax.deviantart.com/\n2-\u0433\u043e : https://lukehumphris.deviantart.com/"
        url = "google.com"
        '''

        if text.strip() != '' or image_path.strip() != '' or url.strip() != '' or len(image_urls): #At least one parameter given
            text = text.strip()
            image_path = image_path.strip()
            if text == '' and image_path == '' and len(image_urls)==0:
                print("No text or image given")
                return

            struct_db = database.Database('structure.db')
            sql = "SELECT " \
                  "telegram_groups.chat_id, " \
                  "telegram_groups.bot_token " \
                  "FROM telegram_groups " \
                  "INNER JOIN projects " \
                  "ON telegram_groups.project_id = projects.id " \
                  "WHERE projects.name = '"+str(self.__project_name)+"'"
            cursor = struct_db.execute(sql)
            row = cursor.fetchone()
            if not row:
                print("No available chat_id an/or bot token found in database")
                return False

            chat_id = row['chat_id']
            bot_token = row['bot_token']

            args = {}
            args['data'] = {
                'chat_id': chat_id
            }

            from json import JSONEncoder

            if url.strip() != '':
                emojis = [
                    u'\U0001f300', #Thumbs up
                    u'\U0001f300', #Cyclone
                    u'\U0001f31f', #Glowing star
                    u'\U0001f33d', #Ear of Maize
                    u'\U0001f340', #Four leaf clover
                    u'\U0001f34c', #Banana
                    u'\U0001f357', #Poultry leg
                    u'\U0001f373', #Cooking
                    u'\U0001f3ae', #Video game
                    u'\U0001f446', #White up pointing backhand index
                    u'\U0001f463', #Footprints
                    u'\U0001f480', #Skull
                    u'\U0001f48a'u'\U0001f48a'u'\U0001f48a', #Pills
                    u'\U0001f52a', #Hocko (knife)
                ]
                args['data']['parse_mode'] = "Markdown"
                args['data']['reply_markup'] = JSONEncoder().encode({
                    "inline_keyboard": [
                        [
                            {
                                'url': url,
                                "text": random.choice(emojis)
                            }
                        ]
                    ]
                })

            if image_path.strip() == '' and len(image_urls) == 0:
                method = "sendMessage"
                args['data']['text'] = text
            else:
                if len(image_urls):  # multiple images at once.
                    # sendMediaGroup method doesn't work with local files at the moment, so we are going to refer to URL
                    method = "sendMediaGroup"
                    media = []
                    for image_url in image_urls:
                        media.append(
                            {
                                'type': 'photo',
                                'media': str(image_url),
                                'caption': str(text)
                            }
                        )
                    args['data']['media'] = JSONEncoder().encode(media)
                else:
                    method = "sendPhoto" + ("?caption=" + text if text != '' else '')
                    args['files'] = {'photo': open(image_path, 'rb')}
            url = "https://api.telegram.org/bot"+bot_token + "/" + method

            r = requests.post(url, **args)
            #print(r.status_code, r.reason, r.content)
            if str(r.status_code) == '200':
                response = json.loads((r.content).decode("utf-8")) # Decode byte literal and convert to Json object
                if response['ok'] == True:
                    result = response['result']
                    #print(json.dumps(result, indent=2))
                    if len(image_urls):
                        return result[0]['message_id'] #returning only the firs one's id
                    return result['message_id']
            return False
