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
        self.__app_id = application_id
        self.__group_id = gid
        self.__project_name = pname
        self.__access_token, _ = self.get_auth_params()
        self.__api = self.get_api(self.__access_token)
        #self.__watermarker = watermarker.Watermarker('assets/watermark_'+pname+'.png', pname + '/notWatermarkedArchive/')


    def add_posts(self, days_number, per_day):
        #self.__watermarker.watermark_folder(folder_from=self.__project_name + r'/new', folder_to=self.__project_name + r'/new')
        posts_time = self.get_posts_time(days_number, per_day)
        posted_counter = 0
        for post_time in posts_time:
            folders = self.get_folders()
            img_unused_folder = folders[0]
            img_used_folder = folders[1]
            if len(os.listdir(img_unused_folder)) == 0:
                print("The folder is empty")
                break
            print('----------------------------------------------')
            # Choosing random image
            image_name = random.choice(os.listdir(img_unused_folder))
            img_path = img_unused_folder + '/' + image_name

            if image_name.find('.gif') == -1:
                with open(img_path, 'rb') as file:
                    img = {'photo': (img_path, file)}
                    # Получаем ссылку для загрузки изображений
                    upload_url = self.get_upload_image_link(img)
                    # Загружаем изображение на url
                    result = self.upload_image(upload_url, img)
                    # Сохраняем фото на сервере и получаем id
                    result = self.save_image_on_server(result)

                # Перемещаем изображение в папку с использованными
                file_control.move_img(img_unused_folder, img_used_folder, image_name)
            else:
                print("'gif' file can't be uploaded\n")
                continue

            print(datetime.fromtimestamp(post_time).strftime('%Y-%m-%d %H:%M:%S'))
            print(image_name)

            # Планируем пост на выбранное время, генерируя тэги и текст
            self.__api.wall.post(
                owner_id=str(-int(self.__group_id)),
                message=self.generate_image_description(image_name),
                publish_date=post_time,
                signed=1,
                attachments=result
            )

            posted_counter += 1

            with open(self.__project_name + '/' + self.__project_name + '_log.txt', 'a') as logfile:
                logfile.write(
                    datetime.fromtimestamp(post_time).strftime('%Y-%m-%d %H:%M:%S') + '\t\t\t' + image_name + '\n')


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
                        "&display=popup&response_type=token&v=5.60".format(app_id=self.__app_id))
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


    def get_posts_time(self, days_number, perDay):
        datetime_to_post = self.get_datetime_starting_point()  # Starting datetime point

        # Getting time to post at, equally distributed
        timeToPost = []
        for x in range(days_number):
            for postIndex in range(perDay):
                # timeToPost.append(19 - int(postIndex*(10/perDay)))
                lowerTimeBorder = (19 - int(postIndex * (10 / perDay)))
                # Выбираем рандомное время для поста в диапазоне двух часов
                datetime_to_post = datetime_to_post.replace(
                    hour=random.randint(lowerTimeBorder, lowerTimeBorder + 2),
                    minute=random.randint(3, 28),
                    microsecond=0
                )
                str_today = datetime_to_post.strftime("%Y-%m-%d %H:%M:%S")
                time_to_post = int(time.mktime(time.strptime(str_today, '%Y-%m-%d %H:%M:%S')))
                timeToPost.append(time_to_post)
            datetime_to_post = datetime_to_post + timedelta(days=1)
        return timeToPost


    def get_datetime_starting_point(self):
        total_posts_planned = self.get_posts(filter="postponed")["count"]
        print(total_posts_planned)
        response = self.get_posts(filter="postponed", offset=total_posts_planned-1)
        if response['count']:  # If there are planned posts, use next day after the last planned date
            last_post = response['items'][len(response['items']) - 1]
            last_post_datetime = datetime.fromtimestamp(last_post['date'])
        else:  # Else - use tomorrow's date
            last_post_datetime = datetime.now()
        return last_post_datetime + timedelta(days=1)  # Next day from last planned post


    def get_posts(self, filter = "all", offset=0):
        owner_id = str(-int(self.__group_id))
        domain = "public" + self.__group_id
        v = 5.58
        if offset == (-1): # Offset should be positive
            offset = 0
        return self.__api.wall.get(owner_id=owner_id, domain=domain, filter=filter, extended=1, offset=offset, v=v)


    def delete_posts(self, post_id = 0, filter = "postponed"):
        owner_id = str(-int(self.__group_id))
        if post_id:
            return self.__api.wall.delete(owner_id=owner_id, post_id=post_id)
        # if post_id = 0, deleting all posts, according to the filter
        else:
            response = 0
            number_of_posts_to_be_deleted = self.get_posts(filter)["count"]
            print(str(number_of_posts_to_be_deleted) + " posts are going to be deleted")
            while len(self.get_posts(filter)["items"]) > 0: #Looping until all posts deleted, because maximum is 20 posts
                posts = self.get_posts(filter)["items"]
                for post in posts:
                    sleep(0.4)  # Time in seconds. Max: 3/sec
                    response = self.__api.wall.delete(owner_id=owner_id, post_id=post["id"])
                    if response == 1:
                        print("post "+str(post["id"])+" deleted")
            return response


    #               images/,      images_used/, new/
    def get_folders(self):
        unused_folder = self.__project_name + r'/images'
        used_folder = self.__project_name + r'/images_used'
        new_folder = self.__project_name + r'/new'
        # If there are images in 'new' folder, using it as an unused one
        if len(file_control.get_image_list(new_folder)) != 0:
            unused_folder = new_folder
        # Else if unused folders are both empty, moving(refreshing) all used images back
        elif len(file_control.get_image_list(unused_folder)) == 0 and len(file_control.get_image_list(unused_folder)) == 0:
            for image in os.listdir(used_folder):
                file_control.move_img(used_folder, unused_folder, image)
        elif len(file_control.get_image_list(unused_folder)) == 0 and len(file_control.get_image_list(unused_folder)) == 0 and len(
                file_control.get_image_list(new_folder)) == 0:
            sys.exit("All folders are empty")
        return [unused_folder, used_folder]


    '''
    def get_image_list(self, path):
        onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
        return onlyfiles
    '''

    '''
    def copy_img(self, img_unused_folder, img_used_folder, image_name):
        source = img_unused_folder + '/' + image_name
        destination = img_used_folder + '/' + image_name
        shutil.copyfile(source, destination)
        print(source + " => " + destination)
        return 1
    '''

    '''
    def move_img(self, img_unused_folder, img_used_folder, image_name):
        source = img_unused_folder + '/' + image_name
        destination = img_used_folder + '/' + image_name
        shutil.move(source, destination)
        print(source + " -> " + destination)
        return 1
    '''


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


    def generate_image_description(self, image_full_name):
        image_name = image_full_name.split('.')[0]
        image_tags = image_name.split(',')
        del image_tags[0]
        print(image_tags)
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
        # description_text = "\n" + "Просто текст..."
        image_description = tags
        return image_description


    def pretty_print(selfself, json_string): #json pretty pring
        print(json.dumps(json_string, indent=2))





    # Method for sending messages, just in case
    def send_message(self, user_id, message, **kwargs):
        data_dict = {
            'user_id': user_id,
            'message': message,
        }
        data_dict.update(**kwargs)
        return self.__api.messages.send(**data_dict)
    # And an example of using it
    '''
        users = [74472774]
        user_text = "test"
        for user_id in users:
            print("User ", user_id)
            res = send_message(api, user_id=user_id, message=user_text)
            time.sleep(1)
            print(res)
    '''