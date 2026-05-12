import datetime

def detection_logic(level : int = 0, parameters = None):
    detection = True
    if parameters is not None:
        temp, rh, time = parameters
        current_time = datetime.datetime.strptime(time, "%Y%m%d%H%M")
        percipitation = 0
    else:
        current_time = datetime.datetime.now()
        percipitation, temp, rh = get_current_weather()
    if level == 0:
        if current_time.hour < 7:
                detection = False
        elif current_time.hour < 8:
            if temp < 12 or rh > 60 or percipitation > 0:        
                detection = False
        elif current_time.hour < 10:        
            if temp < 15 or rh > 70 or percipitation > 0:        
                detection = False
        else:
            if (temp < 20 and rh > 80) or percipitation > 0.5:        
                detection = False        

    return detection, temp, rh, percipitation

def get_current_weather(STATION_ID=10763):
    import requests
    BASE_URL = "https://s3.eu-central-1.amazonaws.com/app-prod-static.warnwetter.de/v16/"
    url = f"{BASE_URL}current_measurement_{STATION_ID}.json"
    try:
        data = requests.get(url, timeout=10).json()
        percipitation, temperature, humidity = data.get("precipitation", {})/10, data.get("temperature", {})/10, data.get("humidity", {})/10
        return percipitation, temperature, humidity
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return 0, 0, 0

if __name__ == "__main__":
    print(get_current_weather())
    a, b, c, d = detection_logic()
    print(f"Detection: {a}, Temp: {b}°C, RH: {c}%, Percipitation: {d}mm")
