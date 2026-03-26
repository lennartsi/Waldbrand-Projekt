import datetime
import pytz
from astral import LocationInfo
from astral.sun import sun

def is_daytime(latitude, longitude, timezone='UTC'):
    """
    Check if current time is between sunrise and sunset for the given coordinates.
    
    Args:
        latitude (float): Latitude in decimal degrees
        longitude (float): Longitude in decimal degrees
        timezone (str): Timezone name (default: 'UTC')
    
    Returns:
        bool: True if current time is between sunrise and sunset, False otherwise
    """
    # Create a location with the provided coordinates
    location = LocationInfo('CustomLocation', 'Region', timezone, latitude, longitude)
    
    # Get the sun's events for today
    tz = pytz.timezone(timezone)
    today = datetime.datetime.now(tz).date()
    sun_times = sun(location.observer, date=today, tzinfo=tz)
    
    # Get current time in the specified timezone
    current_time = datetime.datetime.now(tz)
    
    # Check if current time is between sunrise and sunset
    return sun_times['sunrise'] <= current_time <= sun_times['sunset']

print(is_daytime(49.549495, 11.021824, 'Europe/Berlin'))  # Tennenlohe, Germany