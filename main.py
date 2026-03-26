import datetime
import os
import random
import time
import torch

from transformers import Sam3Processor, Sam3Model
from PIL import Image
import numpy as np
import matplotlib
from VAPIXcamera import VAPIXCamera
from SAM3class import Sam3

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, "Images")
# Ensure Images directory exists
if not os.path.exists(path):
    os.makedirs(path)

which_cam = 0 # 0 for local, 1 for rent

speed = 100

promt="smoke"
time_interval = 0.1  # seconds between each image capture and analysis


if which_cam == 1:
    ip = '195.60.68.14:11066'
    user='VLTuser'
    password='SrJWWEhk'
else:
    ip = '192.44.18.67'
    user='lennart'
    password='7v1wuUGGsE3W2R3GpGbg'
cam=VAPIXCamera(ip, user, password,use_https=False)

sam3=Sam3()

# Loop through presets and analyze images, if an instance is found, move the camera to center it and exit
# time one cycle
start_time = time.time()
preset_no = 1
while True:
    detection = False
    cam.go_to_server_preset_number(preset_no, speed)
    start_time_cam = time.time()
    cam.wait_until_stopped()
    print((preset_no, time.time() - start_time_cam))
    pos = cam.get_ptz_status()

    image=cam.get_current_image()
    timestamp = datetime.datetime.now()
    cam.save_image_with_metadata(path, image, timestamp, pos, detection)

    
    results = sam3.segment(image, promt)
    
    if results['masks'].shape[0]>0:
        detection = True
        print(f"Found {results['masks'].shape[0]} instances of '{promt}' at pan={pos[0]}, tilt={pos[1]}")
        image_with_mask = sam3.overlay_masks(image, results['masks'])
        image_with_mask.show()
        cam.save_image_with_metadata(path, image, timestamp, pos, detection)
        cam.save_image_with_metadata(path, image_with_mask, timestamp, pos, detection, mask=True)

        # Find the lowest point over each mask
        lowest_point = sam3.get_lowest_point(results['masks'])

        cam.center_move(lowest_point[1].item(), lowest_point[0].item(), speed)

        cam.wait_until_stopped()
        

    else:
        print("No masks found.")
        #cam.save_image_with_metadata(path, image, timestamp, pos, detection)

    # time.sleep(time_interval)
    preset_no += 1
    if preset_no == len(cam.list_preset_device().text.splitlines()):
        preset_no = 1
        print("--- %s seconds ---" % (time.time() - start_time))
        exit()
#print(Sam3.segment(sam3, image, promt))
