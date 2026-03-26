import datetime
import os
import random
import time
import torch

from transformers import Sam3Processor, Sam3Model, AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import numpy as np
import matplotlib
from VAPIXcamera import VAPIXCamera
from SAM3class import Sam3
from VLMclass import VLM
from check_daytime import is_daytime

path = r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images"
path_no_smoke = os.path.join(path, "No_smoke_T=0.5_VLM")
path_smoke = os.path.join(path, "Smoke_T=0.5_VLM")
path_A = os.path.join(path_smoke, "Forestfire")
path_B = os.path.join(path_smoke, "Chimney_cloud_fog_industrial")
path_C = os.path.join(path_smoke, "Unsure")

# create folders if they don't exist
os.makedirs(path_no_smoke, exist_ok=True)
os.makedirs(path_A, exist_ok=True)
os.makedirs(path_B, exist_ok=True)
os.makedirs(path_C, exist_ok=True)



ip = '192.44.18.67'
user='lennart'
password='7v1wuUGGsE3W2R3GpGbg'

cam = VAPIXCamera(ip, user, password,use_https=False)
speed = 100

print("Loading sam...")
sam3 = Sam3(threshold=0.5)
promt = "smoke"
print("Loading vlm...")
vlm = VLM()
print("done")
time_interval = 20  # seconds between each image capture and analysis

preset_no = 18
while True:
    if is_daytime(49.549495, 11.021824, 'Europe/Berlin'):
        detection = False
        cam.go_to_server_preset_number(preset_no, speed)
        cam.wait_until_stopped()
        pos = cam.get_ptz_status()
        image = cam.get_current_image()
        timestamp = datetime.datetime.now()

        results = sam3.segment(image, promt)
        max_retries = 3   # prevents infinite loop
        retries = 0

        
        if results['masks'].shape[0]>0:
            detection = True
            #image_with_mask = sam3.overlay_masks(image, results['masks'])
            for mask in results["masks"]:
                while retries <= max_retries:
                    crop_image = sam3.crop_image(image, mask, padding=150)
                    vlm_result = vlm.analyze(crop_image)

                    if retries == max_retries: # if still unsure after max retries, treat as fire and move to original position
                        vlm_result = "A"
                        cam.go_to_server_preset_number(preset_no, speed)
                        cam.wait_until_stopped()
                    if vlm_result == "A" or retries == max_retries:
                        # data_collection_loop()
                        cam.save_image_with_metadata(path_A, image, timestamp, pos, detection)
                        cam.save_image_with_metadata(path_A, crop_image, timestamp, pos, detection, mask=True)
                        lowest_point = sam3.get_lowest_point(results['masks'])
                        break
                    elif vlm_result == "B":
                        cam.save_image_with_metadata(path_B, image, timestamp, pos, detection)
                        cam.save_image_with_metadata(path_B, crop_image, timestamp, pos, detection, mask=True)
                        break
                    elif vlm_result == "C":
                        cam.save_image_with_metadata(path_C, image, timestamp, pos, detection)
                        cam.save_image_with_metadata(path_C, crop_image, timestamp, pos, detection, mask=True)
                        break
                    
                        # lowest_point = sam3.get_lowest_point(results['masks'])
                        # cam.area_zoom(lowest_point[1].item(), lowest_point[0].item(), 250, speed)
                        # cam.wait_until_stopped()
                        # image = cam.get_current_image()
                        # results = sam3.segment(image, promt)
                        # if results['masks'].shape[0]>0:
                        #     mask = results["masks"][0] 
                        # else:
                        #     break
                        # retries += 1
        # else:
            # cam.save_image_with_metadata(path_no_smoke, image, timestamp, pos, detection)
                
        preset_no += 1
        if preset_no == 31:
            preset_no += 1
        if preset_no == 44:
            preset_no = 18
    time.sleep(time_interval)
                    




