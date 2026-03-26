import time
import datetime
from io import BytesIO

from bs4 import BeautifulSoup, FeatureNotFound
from PIL import Image
from requests import auth, get

import os

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, "Images")
# Ensure Images directory exists
if not os.path.exists(path):
    os.makedirs(path)

class VAPIXCamera:
    """
    Module for controlling AXIS cameras using VAPIX
    """

    def __init__(self, ip, user, password, use_https=False):
        self.__username = user
        self.__password = password
        protocol = 'https' if use_https else 'http'
        self.__url = f'{protocol}://{ip}/axis-cgi/com/ptz.cgi'
        self.__image_url = f'{protocol}://{ip}/axis-cgi/jpg/image.cgi'

    @staticmethod
    def __merge(*args) -> dict:
        """
        Given any number of dicts, shallow copy and merge into a new dict,
        precedence goes to key value pairs in latter dicts

        Args:
            *args: argument dictionary

        Returns:
            Return a merged dictionary
        """
        results = {}
        for dictionary in args:
            results.update(dictionary)
        return results

    @staticmethod
    def __parse_response_text(text: str):
        """
        Parse response text with a robust parser fallback.
        """
        try:
            return BeautifulSoup(text, features="lxml")
        except FeatureNotFound:
            return BeautifulSoup(text, features="html.parser")

    def __cmd(self, payload: dict):
        """
        Function used to send commands to the camera
        Args:
            payload: argument dictionary for camera control

        Returns:
            Returns the response from the device to the command sent
        """

        args = {'camera': 1, 'html': 'no', 'timestamp': int(time.time())}

        response = get(self.__url,
                       auth=auth.HTTPDigestAuth(self.__username, self.__password),
                       params=VAPIXCamera.__merge(payload, args))

        if (response.status_code != 200) and (response.status_code != 204):
            soup = self.__parse_response_text(response.text)
            print('%s', soup.get_text())
            if response.status_code == 401:
                exit(1)

        return response

    def absolute_move(self, pan: float, tilt: float, zoom: int, speed: int):
        """
        Operation to move pan, tilt or zoom to a absolute destination.

        Args:
            pan: pans the device relative to the (0,0) position.
            tilt: tilts the device relative to the (0,0) position.
            zoom: zooms the device n steps.
            speed: speed move camera.

        Returns:
            Returns the response from the device to the command sent.
        """
        return self.__cmd({'pan': pan, 'tilt': tilt, 'zoom': zoom, 'speed': speed})
    
    def relative_move(self, pan: float, tilt: float, zoom: int, speed: int):
        """
        Operation for Relative Pan/Tilt and Zoom Move.

        Args:
            pan: pans the device n degrees relative to the current position.
            tilt: tilts the device n degrees relative to the current position.
            zoom: zooms the device n steps relative to the current position.
            speed: speed move camera.

        Returns:
            Returns the response from the device to the command sent.
        """
        return self.__cmd({'rpan': pan, 'rtilt': tilt, 'rzoom': zoom, 'speed': speed})
    
    def center_move(self, pos_x: int, pos_y: int, speed: int):
        """
        Used to send the coordinates for the point in the image where the user clicked.
        This information is then used by the server to calculate the pan/tilt move required to
        (approximately) center the clicked point.

        Args:
            pos_x: value of the X coordinate.
            pos_y: value of the Y coordinate.
            speed: speed move camera.

        Returns:
            Returns the response from the device to the command sent
        """
        pan_tilt = str(pos_x) + "," + str(pos_y)
        return self.__cmd({'center': pan_tilt, 'speed': speed})
    
    def area_zoom(self, pos_x: int, pos_y: int, zoom: int, speed: int):
        """
        Centers on positions x,y (like the center command) and zooms by a factor of z/100.

        Args:
            pos_x: value of the X coordinate.
            pos_y: value of the Y coordinate.
            zoom: zooms by a factor.
            speed: speed move camera.

        Returns:
            Returns the response from the device to the command sent
        """
        x_y_zoom = str(pos_x) + "," + str(pos_y) + "," + str(zoom)
        return self.__cmd({'areazoom': x_y_zoom, 'speed': speed})
    
    def get_current_image(self):
        """
        Get current JPEG image from the camera and convert it to PIL Image.

        Returns:
            PIL Image object of the current camera view
        """
        response = get(self.__image_url,
                       auth=auth.HTTPDigestAuth(self.__username, self.__password), verify=False)

        if response.status_code != 200:
            soup = self.__parse_response_text(response.text)
            print('%s', soup.get_text())
            if response.status_code == 401:
                exit(1)
            return None
        
        return Image.open(BytesIO(response.content))
    
    def get_ptz_status(self):
        """
        Operation to request PTZ status.

        Returns:
            Returns a tuple with the position of the camera (P, T, Z)
        """
        response = self.__cmd({'query': 'position'})
        pan = float(response.text.split()[0].split('=')[1])
        tilt = float(response.text.split()[1].split('=')[1])
        zoom = float(response.text.split()[2].split('=')[1])
        focus = float(response.text.split()[3].split('=')[1])

        return pan, tilt, zoom, focus
    
    def get_status(self):
        """
        Operation to request status.

        Returns:
            Returns a tuple with the status of the camera (moving, autofocus, autoiris)
        """
        response = self.__cmd({'query': 'status'})
        response_parts = response.text.split('\n')
        moving = response_parts[0].split('=')[1].strip()
        autofocus = response_parts[1].split('=')[1].strip()
        autoiris = response_parts[2].split('=')[1].strip()

        return moving, autofocus, autoiris
    
    def get_speed(self):
        """
        Requests the camera's speed of movement.

        Returns:
            Returns the camera's move value.

        """
        resp = self.__cmd({'query': 'speed'})
        return int(resp.text.split()[0].split('=')[1])
    
    def go_to_server_preset_number(self, number: int, speed: int):
        """
        Move to the position associated with the specified preset position number.

        Args:
            number: number of preset position server.
            speed: speed move camera.

        Returns:
            Returns the response from the device to the command sent
        """
        return self.__cmd({'gotoserverpresetno': number, 'speed': speed})
    
    def go_to_device_preset(self, preset_pos: int, speed: int):
        """
        Bypasses the preset pos interface and tells the device to go directly to the preset
        position number stored in the device, where is a device-specific preset position number.

        Args:
            preset_pos: number of preset position device
            speed: speed move camera

        Returns:
            Returns the response from the device to the command sent

        """
        return self.__cmd({'gotodevicepreset': preset_pos, 'speed': speed})
    
    def list_preset_device(self):
        """
        List the presets positions stored in the device.

        Returns:
            Returns the list of presets positions stored on the device.

        """
        return self.__cmd({'query': 'presetposcam'})
    def list_all_preset(self):
        """
        List all available presets position.

        Returns:
            Returns the list of all presets positions.

        """
        response = self.__cmd({'query': 'presetposall'})
        soup = self.__parse_response_text(response.text)
        resp_presets = soup.text.split('\n')
        presets = []

        for i in range(1, len(resp_presets) - 1):
            preset = resp_presets[i].split("=")
            presets.append((int(preset[0].split('presetposno')[1]), preset[1].rstrip('\r')))

        return presets
    
    def go_to_server_preset_name(self, name: str, speed: int):
        """
        Move to the position associated with the preset on server.

        Args:
            name: name of preset position server.
            speed: speed move camera.

        Returns:
            Returns the response from the device to the command sent
        """
        return self.__cmd({'gotoserverpresetname': name, 'speed': speed})
    
    

#-------------MY Functions------------------
    def wait_until_stopped(self):
        """
        Wait until the camera has stopped moving.
        """
        started_moving = False
        for i in range(10):
            if self.get_status()[0] == 'no':
                time.sleep(0.1)
                #print("Not Moving")
            else:
                started_moving = True
                break

        is_moving = self.get_status()[0]
        while is_moving != 'no':
            #print("Moving...")
            time.sleep(0.1)
            is_moving = self.get_status()[0]
        #print("Focusing...")
        self.wait_focus()
        #print("Done focusing.")


    def wait_focus(self):
        """
        Check up to 10 times if the focus value is changing
        
        if it is, wait until it doesn't change for two consecutive checks.
        """
        is_focusing = False
        focus = int(self.get_optics_data()['focus'])
        for i in range(10):  # Check focus status multiple times to confirm
            if focus == int(self.get_optics_data()['focus']):
                time.sleep(0.1)
                # print(f"Focus check {i+1}/10: {focus} (not changing)")
            else:
                is_focusing = True
                break
        if is_focusing:
                #print("actually focusing")
                while True:
                    if focus != int(self.get_optics_data()['focus']):
                        focus = int(self.get_optics_data()['focus'])
                        time.sleep(0.5)
                        # print(f"Waiting for focus to stabilize: {focus}")
                    else:
                        time.sleep(1)
                        if focus == int(self.get_optics_data()['focus']):
                            # print(f"Focus stabilized at: {focus}")
                            return
                        # else:
                            # print(f"Focus changed again, continuing to wait: {focus}"   )



    # def get_focus_status(self):
    #     """
    #     Operation to request focus status.
        
    #     Returns:
    #         Boolean indicating if focus is currently moving
    #     """
    #     focus = self.get_ptz_status()[3]
    #     while
    
    def get_optics_data(self):
        """
        Get detailed optics data from the camera.
        
        Returns:
            Dictionary containing all optics data
        """
        response = self.__cmd({'query': 'position'})
        optics = {}
        for line in response.text.split('\n'):
            if line.strip():
                key, value = line.split('=', 1)
                optics[key.strip()] = value.strip()
        return optics
    


    def get_limits(self):
        r = self.__cmd({'query': 'limits'})
        limits = {}
        for line in r.text.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                limits[k.strip()] = v.strip()
        return limits

    def save_image_with_metadata(self, path, image, timestamp, position, detected, mask=False):
        """
        Save image from camera with metadata including position and detection status.
        
        Args:
            path: directory path where the image will be saved
            timestamp: timestamp string for the filename
            detected: boolean indicating if something was detected (True/False)
        
        Returns:
            filepath if successful, None otherwise
        """
        # Get camera position
        pan, tilt, zoom, focus = position
        
        # Determine yes/no string
        detection_str = "yes" if detected else "no"

        timestamp = timestamp.strftime("%Y%m%d_%H%M%S")

        # Format filename: time_{timestamp}_p:{pan},t:{tilt}_z:{zoom}_{yes/no}.jpg
        if mask:
            filename = f"{timestamp}_({pan},{tilt},{zoom})_{detection_str}_mask.jpg"
        else:
            filename = f"{timestamp}_({pan},{tilt},{zoom})_{detection_str}.jpg"
        filepath = os.path.join(path, filename)
        directory = os.path.dirname(filepath)
        
        # Save image
        if image:
            os.makedirs(directory, exist_ok=True)
            image.save(filepath)
            print(f"Image saved: {filepath}")
            return filepath
        else:
            print("Failed to get image from camera")
            return None


if __name__ == "__main__":
    ip = '192.44.18.67'
    user='lennart'
    password='7v1wuUGGsE3W2R3GpGbg'
    
    cam=VAPIXCamera(ip, user, password,use_https=False)
    # print(cam.list_all_preset())
    cam.go_to_server_preset_number(31, 100)




