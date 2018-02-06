from os import listdir, remove, path, makedirs
from os.path import isfile, join
import shutil


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