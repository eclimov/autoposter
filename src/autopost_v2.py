# -*- coding: utf-8 -*-

import pickle
import webbrowser
from urllib.parse import parse_qs
from datetime import datetime, timedelta
import vk
import random
import time
import os
import sys
import requests
import json
import watermarker
import shutil
from os import listdir
from os.path import isfile, join
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

    def __init__(self, application_id, gid, pname):
        self.__project_name = pname

        self.__img_folder_path_new = pname + '/images_new'
        self.__img_folder_path_working = pname + '/images_working'
        self.__db = database.Database(pname+'/database.db')
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
                  "    artwork_id         INTEGER       NOT NULL," \
                  "    post_date          DATETIME      DEFAULT (DateTime('now'))" \
                  "                                     NOT NULL" \
                  ");"
        self.__db.execute(sqlInitLog)

        self.refresh_image_queue()

        self.__app_id = application_id
        self.__group_id = gid
        self.__access_token, _ = self.get_auth_params()
        self.__api = self.get_api(self.__access_token)
        #self.__watermarker = watermarker.Watermarker('assets/watermark_'+pname+'.png', pname + '/notWatermarkedArchive/')

    def get_group_id(self):
        return self.__group_id

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
            disk_image_name = image['name'] + "," + image_tags_string + '.' + image['extension']
            file_control.rename_img(self.__img_folder_path_new, new_image, disk_image_name)
            sql = "INSERT INTO " + self.__project_name + "(name,tags) VALUES ('" + db_image_name + "','" + image_tags_string + "')"
            cursor = self.__db.execute(sql)
            print("Row inserted in DB: id=" + str(cursor.lastrowid))
            file_control.move_img(self.__img_folder_path_new, self.__img_folder_path_working, disk_image_name)

    def db_cleanup(self):
        working_images_list = file_control.get_image_list(self.__img_folder_path_working)
        if len(working_images_list) != 0:
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
        image_extension = image_full_name.split('.')[1]
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
                        "&client_secret=*************"
                        "&display=popup&response_type=token&v=5.81".format(app_id=self.__app_id))
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


    def get_posts(self, filter = "all", offset=0):
        owner_id = str(-int(self.__group_id))
        domain = "public" + self.__group_id
        v = 5.81
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


    def generate_image_tags(self, image_tags):
        image_tags = image_tags.split(",")
        tag1 = ""
        tag2 = ""
        if image_tags:
            tag1 = random.choice(image_tags)
            image_tags.remove(tag1)
            tag1 = " #" + tag1
            if image_tags:
                tag2 = random.choice(image_tags)
                image_tags.remove(tag2)
                tag2 = " #" + tag2
        tags = '#' + self.__project_name + ' ' + tag1 + tag2
        return tags


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


    def create_post_schedule(self, days_number, perDay):
        schedule = []
        # Creating temporary table. Move all logs into it and process the table in loop to avoid nicorrect choices
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
                tags = self.generate_image_tags(image['tags'])
                self.__db.execute(
                    "INSERT INTO activity_log_temp(artwork_id, post_date) "
                    "VALUES(" + str(image['id']) + ", '" + datetime_to_post_string + "')"
                )
                schedule.append(
                    {
                        'image': image,
                        'datetime': datetime_to_post,
                        'datetime_string': datetime_to_post_string,
                        'datetime_unix': datetime_to_post_unix,
                        'tags': tags
                    }
                )
        self.__db.execute("DROP TABLE activity_log_temp")
        return schedule


    def choose_image(self, timestamp, activity_log_table='activity_log'):
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
                'tags': result['tags'],
                'extension': result['name'].split('.')[1]
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


    def add_posts(self, days_number, per_day):
        if days_number < 1 or per_day < 1:
            print("Number of posts and number of days cannot be less than 1")
            return
        if len(os.listdir(self.__img_folder_path_working)) == 0:
            print("Working folder is empty")
            return
        planned_posts = self.create_post_schedule(days_number, per_day)

        for post in planned_posts:
            post_time = post['datetime']
            post_time_string = post['datetime_string']
            post_time_unix = post['datetime_unix']
            image = post['image']
            tags = post['tags']
            if image == False:
                print("No applicable images found in database for day " + post_time_string)
                continue

            if self.isEnglish(image['tags']):
                image_physical_name = image['name'] + ',' + image['tags'] + '.' + image['extension']
            else: # If image name contains cyrillic characters, that cannot be normally sent to API
                image_temp_name = "temp." + image['extension']
                file_control.rename_img(
                    self.__project_name + '/images_working/',
                    image['name'] + ',' + image['tags'] + '.' + image['extension'],
                    image_temp_name
                )
                image_physical_name = image_temp_name

            try:
                if image_physical_name.find('.gif') == -1:
                    img_path = self.__project_name + '/images_working/' + image_physical_name
                    with open(img_path, 'rb') as file:
                        img = {'photo': (img_path, file)}
                        # Получаем ссылку для загрузки изображений
                        upload_url = self.get_upload_image_link(img)
                        # Загружаем изображение на url
                        result = self.upload_image(upload_url, img)
                        # Сохраняем фото на сервере и получаем id
                        result = self.save_image_on_server(result)
                else:
                    print("'gif' file can't be uploaded\n")
                    continue
            except Exception as e:
                print('*'+str(e)+'*')
            finally:
                # If image name contains cyrillic characters, that cannot be normally sent to API
                if not self.isEnglish(image['tags']):
                    image_temp_name = "temp." + image['extension']
                    file_control.rename_img(
                        self.__project_name + '/images_working/',
                        image_temp_name,
                        image['name'] + ',' + image['tags'] + '.' + image['extension']
                    )
                    image_physical_name = image['name'] + ',' + image['tags'] + '.' + image['extension']

            vk_post_id = self.vk_post(tags=tags, publish_date=post_time_unix, attachments=result)

            # Creating log
            self.__db.execute(
                "INSERT INTO activity_log(artwork_id, post_date) "
                "VALUES("+str(image['id'])+", '"+post_time_string+"')"
            )

            with open(self.__project_name + '/' + self.__project_name + '_log.txt', 'a') as logfile:
                logfile.write(post_time_string + '\t\t\t' + image_physical_name + '\n')

            yield {
                'vk_post_id': vk_post_id,
                'image_path': self.__project_name + '/images_working/' + image_physical_name,
                'post_time': post_time_string,
                'tags': image['tags']
            }

    def vk_post(self, tags='', message='', publish_date='', attachments='', signed=1):
        args = {}
        text = ''

        if tags.strip() != '':
            text = tags+'\n' if message!='' else tags
        if message.strip() != '':
            text += message

        args['message'] = text
        args['signed'] = signed
        if publish_date != '':
            args['publish_date'] = publish_date
        args['owner_id'] = str(-int(self.__group_id))
        if attachments != '':
            args['attachments'] = attachments

        return self.__api.wall.post(**args) #post_id


    def delete_posts(self, post_id = 0, filter = "postponed"):
        owner_id = str(-int(self.__group_id))
        if post_id:
            self.__api.wall.delete(owner_id=owner_id, post_id=post_id)
            yield "post " + str(post_id) + " deleted"
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
                        yield "post "+str(post["id"])+" deleted"


    # Get certain number of values values, distributed within given range
    # returns [a1, a2, a3, a4, ... , an]
    def distribution(self, start, end, n):
        if n < 1:
            raise Exception("behaviour not defined for n<1")
        if n == 1:
            return [start]
        step = (end - start) / float(n - 1)
        return [int(round(start + x * step)) for x in range(n)]


    def telegram_post(self, text='', image_path=''):
        text = text.strip()
        image_path = image_path.strip()
        if text == '' and image_path == '':
            print("No text or image given")
            return
        args = {}
        args['data'] = {'chat_id': "@left4dead3"}
        if image_path == '':
            method = "sendMessage"
            args['data']['text'] = text
        else:
            method = "sendPhoto" + ("?caption="+text if text != '' else '')
            args['files'] = {'photo': open(image_path, 'rb')}
        bot_token = "375621432:AAFeTgdE4PDPfLrIKAwO0nerfvpWYQJjXBU"
        url = "https://api.telegram.org/bot"+bot_token + "/" + method
        r = requests.post(url, **args)
        print(r.status_code, r.reason, r.content)


