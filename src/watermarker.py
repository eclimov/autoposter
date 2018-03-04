"""
Created on 1 окт. 2016 г.

@author: Edik
"""

import file_control
# import os
from PIL import Image
# from PIL import ImageDraw
# from PIL import ImageFont
# from PIL import ImageEnhance


class Watermarker:
    def __init__(self, watermark_path, not_watermarked_archive_path):
        self.__watermark_path = watermark_path
        self.__not_watermarked_archive_path = not_watermarked_archive_path

    def watermark_folder(self, folder_from, folder_to):
        print('**Watermarking**\nfrom: ' + folder_from)
        print('to: ' + folder_to)
        image_list = file_control.get_image_list(folder_from)
        print(image_list)
        for image_name in image_list:
            image_path = folder_from + '/' + image_name
            try:
                #with Image.open(image_path) as image:
                file_control.copy_img(folder_from + '/', self.__not_watermarked_archive_path, image_name)
                self.add_watermark(image_path)
                file_control.move_img(folder_from + '/', folder_to + '/', image_name)
            except Exception as e:
                print("Error while watermarking image: '"+image_path+"'\n")
                print(str(e))
                return False
        print('All images have been watermarked and stored in folder: ' + folder_to + '\n')
        return True

    def add_watermark(self, file_path):
        # watermark = Image.open('assets/watermark_' + projectName + '.png', 'r')
        watermark = Image.open(self.__watermark_path, 'r')
        with Image.open(file_path) as background:
            # MyVk.copy_img(folder_from + '/', projectName + '/notWatermarkedArchive/', image)
            # watermark_w, watermark_h = watermark.size
            bg_w, bg_h = background.size
            if bg_w > bg_h:
                basewidth = bg_w / 4
            elif bg_w == bg_h:
                basewidth = bg_w / 3
            else:
                basewidth = bg_w / 2
            wpercent = (basewidth / float(watermark.size[0]))
            hsize = int((float(watermark.size[1]) * float(wpercent)))
            watermark = watermark.resize((int(basewidth), int(hsize)), Image.ANTIALIAS)
            watermark_w, watermark_h = watermark.size
            # offset = (int((bg_w - img_w) / 2), int((bg_h - img_h) / 2))
            position_x = bg_w - watermark_w-watermark_h/5
            position_y = bg_h - watermark_h
            offset = int(position_x), int(position_y)
            background.paste(watermark, offset, watermark)
            background.save(file_path)
            #MyVk.move_img(folder_from + '/', folder_to + '/', image)