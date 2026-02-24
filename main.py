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

which_cam = "forst"
if which_cam == "rent":
    ip = '195.60.68.14:11066'
    user='VLTuser'
    password='SrJWWEhk'
else:
    ip = '192.44.18.67'
    user='lennart'
    password='7v1wuUGGsE3W2R3GpGbg'
cam=VAPIXCamera(ip, user, password,use_https=False)
time_interval = 5  # seconds between each image capture and analysis

sam3=Sam3()
promt="tower of a church"


while True:
    detection = False
    cam.relative_move(45, 0, 0, 100)
    cam.wait_until_stopped()
    pos = cam.get_ptz_status()

    image=cam.get_current_image()
    timestamp = datetime.datetime.now()
    
    resulsts = sam3.segment(image, promt)
    print("Analysing image at pan: {}, tilt: {}".format(pos[0], pos[1]))
    if resulsts['masks'].shape[0]>0:
        detection = True
        print(f"Found {resulsts['masks'].shape[0]} instances of '{promt}' at pan={pos[0]}, tilt={pos[1]}")
        cam.save_image_with_metadata(image, timestamp, pos, detection)
        lowest_points = []
        
        # Find the lowest point over each mask
        for i in range(resulsts['masks'].shape[0]):
            lowest_points.append(sam3.get_lowest_point(resulsts['masks'][i]))
        arr = np.array(lowest_points)
        lowest_point = arr[np.argmax(arr[:, 0])]

        cam.area_zoom(lowest_point[1].item(), lowest_point[0].item(), pos[2]+100, 100)
        # cam.wait_until_stopped()
        exit()
    else:
        print("No masks found.")
        cam.save_image_with_metadata(image, timestamp, pos, detection)
    time.sleep(time_interval)
#print(Sam3.segment(sam3, image, promt))
