import datetime

class DetectionOrchestrator:
    def __init__(self, cam, sam3, vlm_model, logger, image_paths):
        self.cam = cam
        self.logger = logger
        self.sam3 = sam3
        self.vlm_model = vlm_model
        self.image_paths = image_paths

    def detection_pipeline(self, pos_value):
        vlm_result = None
        image, ptz_pos = self.cam.get_preset_image(pos_value)
        timestamp = datetime.datetime.now()
        detection_data = {
            "timestamp": timestamp,
            "position": pos_value,
            "ptz_pos": ptz_pos,
            "image_filepaths": [],
            "lowest_point": None,
        }

        results = self.sam3.segment(image)
        if results['masks'].shape[0] > 0:
            mask_no = 0
            for mask in results["masks"]:
                crop_image = self.sam3.crop_image(image, mask, padding=150)
                vlm_result = self.vlm_model.analyze(crop_image).decision
                print(f"VLM result: {vlm_result}")

                if vlm_result:
                    filepath = self.cam.save_image_with_metadata(self.image_paths['forestfire'], crop_image, timestamp, ptz_pos, detected=True, mask=mask_no)
                    filepath_original = self.cam.save_image_with_metadata(self.image_paths['forestfire'], image, timestamp, ptz_pos, detected=True)
                    detection_data["lowest_point"] = self.sam3.get_lowest_point_single_mask(mask)
                    detection_data["image_filepaths"].extend((filepath, filepath_original))
                    return vlm_result, detection_data
                
                elif vlm_result is False:
                    filepath = self.cam.save_image_with_metadata(self.image_paths['nonfire'], crop_image, timestamp, ptz_pos, detected=False, mask=mask_no)
                    filepath_original = self.cam.save_image_with_metadata(self.image_paths['nonfire'], image, timestamp, ptz_pos, detected=False)
                else:
                    filepath = self.cam.save_image_with_metadata(self.image_paths['uncertain'], crop_image, timestamp, ptz_pos, detected=False)
                    filepath_original = self.cam.save_image_with_metadata(self.image_paths['uncertain'], image, timestamp, ptz_pos, detected=False)
                mask_no += 1
        return vlm_result, detection_data
    
    def get_zoomed_video(self, alert_id, detection_data):
        lowest_point = detection_data["lowest_point"]
        timestamp = detection_data["timestamp"]
        ptz_pos = detection_data["ptz_pos"]
        self.cam.area_zoom(lowest_point[1].item(), lowest_point[0].item())
        filepath_zoomed = self.cam.save_image_with_metadata(self.image_paths['forestfire'], self.cam.get_current_image(), timestamp, ptz_pos, detected=True, zoomed=True)
        video_path = self.cam.save_video_ffmpeg(path=self.image_paths['forestfire'], alert_id=alert_id, duration_seconds=10)
        detection_data["image_filepaths"].append(filepath_zoomed)
        return detection_data["image_filepaths"], video_path

    def create_alarm_package(self, detection_data, temp, rh, precipitation):
        alert_id = f"Cam{self.cam.cam_no}_{detection_data['timestamp'].strftime('%Y%m%d%H%M%S')}"
        detection_data["image_filepaths"], video_path = self.get_zoomed_video(alert_id, detection_data)
        alarm_package = {
            "alert_id": alert_id,
            "pos_value": detection_data['position'],
            "ptz_pos": detection_data['ptz_pos'],
            "weather": [temp, rh, precipitation],
            "image_paths": detection_data['image_filepaths'],
            "video_path": video_path,
        }
        return alarm_package