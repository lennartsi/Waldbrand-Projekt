import time
from io import BytesIO

from bs4 import BeautifulSoup
from PIL import Image
from requests import auth, get

import os

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, "current_view.jpg")

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
            soup = BeautifulSoup(response.text, features="lxml")
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
    
    def get_current_image(self):
        """
        Get current JPEG image from the camera and convert it to PIL Image.

        Returns:
            PIL Image object of the current camera view
        """
        response = get(self.__image_url,
                       auth=auth.HTTPDigestAuth(self.__username, self.__password), verify=False)

        if response.status_code != 200:
            soup = BeautifulSoup(response.text, features="lxml")
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

        return pan, tilt, zoom
    
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
    

#-------------MY Functions------------------
    def wait_until_stopped(self):
        """
        Wait until the camera has stopped moving.
        """
        is_moving = self.get_status()[0]
        while is_moving != 'no':
            time.sleep(0.5)
            is_moving = self.get_status()[0]

    def get_limits(self):
        r = self.__cmd({'query': 'limits'})
        limits = {}
        for line in r.text.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                limits[k.strip()] = v.strip()
        return limits

ip='195.60.68.14:11115'
url = f"http://{ip}/axis-cgi/com/ptz.cgi"
user='VLTuser'
password='pMycBxxn'
cam=VAPIXCamera(ip, user, password,use_https=False)
is_moving=cam.get_status()[0]

# cam.absolute_move(100, 0, 1, 100)
# cam.wait_until_stopped()
# time.sleep(3)
cam.center_move(0,0, 100)
cam.wait_until_stopped()


print(cam.get_ptz_status())
#print(cam.get_status())
#cam.get_current_image().save(path)




