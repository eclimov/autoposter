'''
Created on 7 авг. 2016 г.

@author: Edik
'''

# -*- encoding: utf-8 -*-

from __future__ import unicode_literals
import pprint
from urllib.parse import parse_qs
import webbrowser
import pickle
from datetime import datetime, timedelta
import random
import vk
import time
import requests
import json
import pymysql
import shutil
import os
import sys
import sqlite3

# file, where auth data is saved
AUTH_FILE = '.auth_data'
# chars to exclude from filename
FORBIDDEN_CHARS = '/\\\?%*:|"<>!'

def get_saved_auth_params():
    access_token = None
    user_id = None
    try:
        with open(AUTH_FILE, 'rb') as pkl_file:
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
    return access_token, user_id


def save_auth_params(access_token, expires_in, user_id):
    expires = datetime.now() + timedelta(seconds=int(expires_in))
    with open(AUTH_FILE, 'wb') as output:
        pickle.dump(access_token, output)
        pickle.dump(expires, output)
        pickle.dump(user_id, output)


def get_auth_params(APP_ID):
    auth_url = ("https://oauth.vk.com/authorize?client_id={app_id}"
                "&redirect_uri=https://oauth.vk.com/blank.html"
                "&scope=notify,friends,photos,audio,video,docs,notes,pages,status,offers,questions,wall,groups,messages,notifications,stats,ads,offline"
                "&client_secret=B1ESDOkPPNa9Mxootnb0"
                "&display=popup&response_type=token&v=5.60".format(app_id=APP_ID))
    webbrowser.open_new_tab(auth_url)
    redirected_url = input("Paste here url you were redirected:\n")
    aup = parse_qs(redirected_url)
    aup['access_token'] = aup.pop(
        'https://oauth.vk.com/blank.html#access_token')
    save_auth_params(aup['access_token'][0], aup['expires_in'][0],
                     aup['user_id'][0])
    return aup['access_token'][0], aup['user_id'][0]


def get_api(access_token):
    session = vk.Session(access_token=access_token)
    return vk.API(session)


def send_message(api, user_id, message, **kwargs):
    data_dict = {
        'user_id': user_id,
        'message': message,
    }
    data_dict.update(**kwargs)
    return api.messages.send(**data_dict)


def get_image_list(path):
    from os import listdir
    from os.path import isfile, join
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
    return onlyfiles


def get_upload_image_link(access_token, img, gid):
    method_url = 'https://api.vk.com/method/photos.getWallUploadServer?'
    data = dict(access_token=access_token, gid=gid)
    response = requests.post(method_url, data)
    result = json.loads(response.text)
    upload_url = result['response']['upload_url']
    return upload_url


def upload_image(upload_url, img):
    response = requests.post(upload_url, files=img)
    result = json.loads(response.text)
    return result


def save_image_on_server(access_token, gid, result):
    method_url = 'https://api.vk.com/method/photos.saveWallPhoto?'
    data = dict(access_token=access_token, gid=gid, photo=result['photo'], hash=result['hash'], server=result['server'])
    response = requests.post(method_url, data)
    result = json.loads(response.text)['response'][0]['id']
    return result


def generate_image_description(folder, image_full_name):
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
    tags = '#' + folder + ' ' + tag1 + tag2
    # description_text = "\n" + "Просто текст..."
    image_description = tags
    return image_description


def move_img(img_unused_folder, img_used_folder, image_name):
    source = img_unused_folder + '/' + image_name
    destination = img_used_folder + '/' + image_name
    shutil.move(source, destination)
    print(source + " -> " + destination)
    return 1


def copy_img(img_unused_folder, img_used_folder, image_name):
    source = img_unused_folder + '/' + image_name
    destination = img_used_folder + '/' + image_name
    shutil.copyfile(source, destination)
    print(source + " => " + destination)
    return 1

#               images/,      images_used/, new/
def get_folders(unused_folder, used_folder, new_folder):
    # If there are images in 'new' folder, using it as an unused one
    if len(get_image_list(new_folder)) != 0:
        unused_folder = new_folder
    # Else if unused folders are both empty, moving(refreshing) all used images back
    elif len(get_image_list(unused_folder)) == 0 and len(get_image_list(unused_folder)) == 0:
        for image in os.listdir(used_folder):
            move_img(used_folder, unused_folder, image)
    elif len(get_image_list(unused_folder))==0 and len(get_image_list(unused_folder))==0 and len(get_image_list(new_folder))==0:
        sys.exit("All folders are empty")
    return [unused_folder, used_folder]

def get_datetime_starting_point(api, gid):
    owner_id = str(-int(gid))
    domain = "public"+gid
    filter = "postponed"
    v = 5.58

    response = api.wall.get(owner_id=owner_id, domain=domain, filter=filter, v=v)
    if response['count']: #If there are planned posts, use next day after the last planned date
        last_post = response['items'][response['count']-1]
        last_post_datetime = datetime.fromtimestamp(last_post['date'])
    else: #Else - use tomorrow's date
        last_post_datetime = datetime.now()
    return last_post_datetime + timedelta(days=1)  # Next day from last planned post

def get_posts_time(api, gid, total, perDay):
    datetime_to_post = get_datetime_starting_point(api, gid) #Starting datetime point
    total = total

    # Getting time to post at, equally distributed
    timeToPost = []
    for x in range(total):
        for postIndex in range(perDay):
            #timeToPost.append(19 - int(postIndex*(10/perDay)))
            lowerTimeBorder = (19 - int(postIndex*(10/perDay)))
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


def add_posts(app_id, gid, folder, total, perDay):
    '''
    con = sqlite3.connect('posts.db')
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, firstName VARCHAR(100), secondName VARCHAR(30))')
    con.commit()
    cur.execute('INSERT INTO users (id, firstName, secondName) VALUES(NULL, "Guido", "van Rossum")')
    con.commit()
    print(cur.lastrowid)
    cur.execute('SELECT * FROM users')
    print(cur.fetchall())
    con.close()
    return
    '''
    access_token, _ = get_saved_auth_params()
    if not access_token or not _:
        access_token, _ = get_auth_params(app_id)
    api = get_api(access_token)

    ################################################################################
    posts_time = get_posts_time(api, gid, total, perDay)
    ################################################################################

    '''
    users = [74472774]
    user_text = "test"
    for user_id in users:
        print("User ", user_id)
        res = send_message(api, user_id=user_id, message=user_text)
        time.sleep(1)
        print(res)
    '''

    posted_counter = 0

    for post_time in posts_time:
        folders = get_folders(folder + r'/images', folder + r'/images_used', folder + r'/new')
        img_unused_folder = folders[0]
        img_used_folder = folders[1]
        print('----------------------------------------------')
        # Choosing random image
        image_name = random.choice(os.listdir(img_unused_folder))
        img_path = img_unused_folder + '/' + image_name

        if image_name.find('.gif') == -1:
            with open(img_path, 'rb') as file:
                img = {'photo': (img_path, file)}
                # Получаем ссылку для загрузки изображений
                upload_url = get_upload_image_link(access_token, img, gid)
                # Загружаем изображение на url
                result = upload_image(upload_url, img)
                # Сохраняем фото на сервере и получаем id
                result = save_image_on_server(access_token, gid, result)

            # Перемещаем изображение в папку с использованными
            move_img(img_unused_folder, img_used_folder, image_name)
        else:
            print("'gif' file can't be uploaded\n")
            continue

        print(datetime.fromtimestamp(post_time).strftime('%Y-%m-%d %H:%M:%S'))
        print(image_name)

        # Планируем пост на выбранное время, генерируя тэги и текст
        api.wall.post(
            owner_id=str(-int(gid)),
            message=generate_image_description(folder, image_name),
            publish_date=post_time,
            signed=1,
            attachments=result
        )

        posted_counter += 1

        with open(folder + '/' + folder + '_log.txt', 'a') as logfile:
            logfile.write(datetime.fromtimestamp(post_time).strftime('%Y-%m-%d %H:%M:%S') + '\t\t\t' + image_name + '\n')

    '''
    conn = pymysql.connect(host='localhost', user='root', passwd='', db='l4d3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM image_genre')
    #print(cursor.description)
    for row in cursor:
        print(row[1])

    cursor.close()
    conn.close()
    '''
    return posted_counter
