from requests import auth, get

ip='195.60.68.14:11115'
url = f"http://{ip}/axis-cgi/com/ptz.cgi"
user='VLTuser'
password='pMycBxxn'


params = {
    "pan": 10,     # -180 to 180
    "tilt": 0,  # -90 to 90
    "zoom": 0,   # optional
    "speed": 100  # optional
}
get(url, params=params,
                 auth=auth.HTTPDigestAuth(user, password))