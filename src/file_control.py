from os import listdir, remove, path, makedirs
from os.path import isfile, join
import shutil
import string
import random


def get_image_list(path):
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
    return onlyfiles

def copy_img(folder_from, folder_to, image_name):
    source = folder_from + '/' + image_name
    destination = folder_to + '/' + image_name
    shutil.copyfile(source, destination)
    print(source + " => " + destination)
    return 1

def copy_img1(img_path_old, img_path_new): #Copies image, basing on provided paths
    shutil.copyfile(img_path_old, img_path_new)
    return 1

def move_img(folder_from, folder_to, image_name):
    source = folder_from + '/' + image_name
    destination = folder_to + '/' + image_name
    shutil.move(source, destination)
    print(source + " -> " + destination)
    return 1

def rename_img(img_folder, old_name, new_name):
    shutil.move(img_folder + '/' + old_name, img_folder + '/' + new_name)
    return 1

def rename_img1(img_path_old, img_path_new): #Renames/moves image, basing on provided paths
    shutil.move(img_path_old, img_path_new)
    return 1

def delete_file(file_path):
    if isfile(file_path):
        remove(file_path)
        return 1
    return 0

def create_folder(folder_path):
    if not path.exists(folder_path):
        makedirs(folder_path)
        return True
    return False

# Returns dictionary{'name', 'tags', 'extension'}
def parse_image_name(image_full_name):
    image_name_with_tags = image_full_name.split('.')[0]
    image_name = image_name_with_tags.split(',')[0]
    image_extension = image_full_name.split('.')[-1]  # Last element of "split()" result
    image_tags = image_name_with_tags.split(',')
    del image_tags[0]
    return {'name': image_name, 'tags': image_tags, 'extension': image_extension}

def is_valid_name(name, size):
    if len(name) != size:
        return False
    for i in name:
        if not i.isalnum() or not i.isupper():
            return False
    return True

def generate_alphanumeric(size, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def isEnglish(s):
    try:
        s.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True


# Get certain number of values values, distributed within given range
# returns [a1, a2, a3, a4, ... , an]
def distribution(start, end, n):
    if n < 1:
        raise Exception("behaviour not defined for n<1")
    if n == 1:
        return [end]
    step = (end - start) / float(n - 1)
    return [int(round(start + x * step)) for x in range(n)]