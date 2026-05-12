import ast
import json
from datetime import datetime, timedelta
from pathlib import Path
from astral import LocationInfo
from astral.sun import sun
from operator import add
import time
from detection_cutoff import detection_logic

def local_to_utc(time_str):
    '''Converts local time stirng to UTC time string. Check DST for provided date. If none provided, check for current date.'''
    if len(time_str) == 15:
        local_time = datetime.strptime(time_str, "%Y%m%d_%H%M%S")
        dst = time.localtime(local_time.timestamp()).tm_isdst
        utc_string = (local_time - timedelta(hours=1+dst)).strftime("%Y%m%d_%H%M%S")
    else:
        dst = time.localtime().tm_isdst
        local_time = datetime.strptime(time_str, "%H%M%S")
        utc_string = (local_time - timedelta(hours=1+dst)).strftime("%H%M%S")
    return utc_string



def analyze_saved_data_time(data_path, date):
    total = 0
    quater_hours_sunrise = [0,0,0,0,0,0,0,0]
    quater_hours_sunset = [0,0,0,0,0,0,0,0] 
    
    sun = get_sunrise_sunset(date)
    # create a list with 0 values for quarter-hour intervals between sunrise and sunset for easier counting
    quater_hours_day = [0] * (int((sun[1] - sun[0]).total_seconds() // (15 * 60)) + 1)
    date_strf = date.strftime('%Y%m%d')

    for image_path in data_path.iterdir():
        if date_strf in image_path.name:
            total += 1
            dt = datetime.strptime(image_path.name.split('_(')[0], "%Y%m%d_%H%M%S")
            time = sun[0]
            for i in range(len(quater_hours_day)):
                if time <= dt < time + timedelta(minutes=15):
                    quater_hours_day[i] += 1
                    break
                time += timedelta(minutes=15)

            quater_hours_sunrise = quater_hours_day[:8]
            quater_hours_sunset = quater_hours_day[-8:]
    return total, quater_hours_sunrise, quater_hours_sunset, quater_hours_day, sun

def load_weather_data():
    import pandas as pd
    url_recent = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/recent/10minutenwerte_TU_03668_akt.zip"
    df_recent = pd.read_csv(url_recent, compression="zip", sep=";")
    df_recent.columns = df_recent.columns.str.strip()
    url_now = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/now/10minutenwerte_TU_03668_now.zip"
    df_now = pd.read_csv(url_now, compression="zip", sep=";")
    df_now.columns = df_now.columns.str.strip()
    df = pd.concat([df_recent, df_now], ignore_index=True)
    return df

def analyze_T_RH(data_path, date_str):
    '''Given a specific date in the format YYYYMMDD, returns the temperature and relative humidity values for each image in data_path.'''
    import pandas as pd
    temperatures = []
    humidities = []
    url_recent = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/recent/10minutenwerte_TU_03668_akt.zip"
    df_recent = pd.read_csv(url_recent, compression="zip", sep=";")
    df_recent.columns = df_recent.columns.str.strip()
    url_now = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/now/10minutenwerte_TU_03668_now.zip"
    df_now = pd.read_csv(url_now, compression="zip", sep=";")
    df_now.columns = df_now.columns.str.strip()
    df = pd.concat([df_recent, df_now], ignore_index=True)
    df = load_weather_data()
    # cut all content not from the given date
    df["MESS_DATUM"] = df["MESS_DATUM"].astype(str).str.zfill(12)
    day_df = df[df["MESS_DATUM"].str.startswith(date_str)].copy()
    for image_path in data_path.iterdir():
        if date_str in image_path.name:
            time_date_str = local_to_utc(image_path.name.split('_(')[0])[:-3] + "0"
            time_str = time_date_str[-4:]
            for i in range(len(day_df)):
                if time_str in str(day_df.iloc[i]["MESS_DATUM"])[-4:]:
                    temperatures.append(day_df.iloc[i]["TT_10"])
                    humidities.append(day_df.iloc[i]["RF_10"])
    return temperatures, humidities

def frequency_T_RH(temp, rh):
    '''Given lists of temperature and relative humidity values, returns the frequency of each combination of temperature and relative humidity.'''
    temps = [0]*20
    rhs = [0]*10
    for t in temp:
        if t<0:
            temps[0] += 1
        elif t>20:
            temps[-1] += 1
        else:
            temps[int(t)] += 1
    for r in rh:
        rhs[int(r//10)] += 1
    return temps, rhs

def get_sunrise_sunset(date):
    location = LocationInfo("Nürnberg", "Germany", "Europe/Berlin", 49.4521, 11.0767)
    sun_data = sun(location.observer, date, tzinfo=location.timezone)
    # return offset naive times for easier comparison with image timestamps
    return sun_data['sunrise'].replace(tzinfo=None), sun_data['sunset'].replace(tzinfo=None)

def get_current_weather(STATION_ID=10763):
    import requests
    BASE_URL = "https://s3.eu-central-1.amazonaws.com/app-prod-static.warnwetter.de/v16/"
    url = f"{BASE_URL}current_measurement_{STATION_ID}.json"
    data = requests.get(url, timeout=10).json()
    percipitation, temperature, humidity = data.get("precipitation", {})/10, data.get("temperature", {})/10, data.get("humidity", {})/10
    return percipitation, temperature, humidity


def get_wbi(date_str=None):
    import pandas as pd
    try:
        url = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/fire_danger_index/woodland/forecast/recent/derived_germany_fire_danger_index_woodland_forecast_recent_3668_v2-3--0.csv.gz"

        df = pd.read_csv(url, compression="gzip", sep=";")
        df.columns = df.columns.str.strip()
        if date_str:
            date_today = date_str
        else:
            date_today = datetime.today().strftime("%Y%m%d")
        for i in range(len(df)):
            if date_today in str(df.iloc[i]["Termin"]):
                today_data = df.iloc[i]
                break
        
        wbi = today_data["wbi_0"]
        print(f"Waldbrandindex am {today_data['Termin']}: {wbi}")
        return int(wbi)
    except Exception as e:
        print(f"Error occurred while fetching WBI data: {e}")
        return None


def raw_data_per_image(data_path):
    import pandas as pd
    if "chimney" in str(data_path).lower():
        if "qwen" in str(data_path).lower():
            filename = "raw_data_base_qwen_Chimney.json"
        else:
            filename = "raw_data_Chimney.json"
    elif "forest" in str(data_path).lower():
        if "qwen" in str(data_path).lower():
            filename = "raw_data_base_qwen_Forestfire.json"
        else:
            filename = "raw_data_Forestfire.json"
    filename_path = Path(__file__).resolve().parent / filename
    try:
        with open(filename_path, "r", encoding="utf-8") as f:
            values = json.load(f)
    except FileNotFoundError:
        print(f"No existing raw data file found at {filename_path}. A new one will be created.")
        values = {}

    df = load_weather_data()

    wbi_dates = {}
    day_dfs = {}
    for image_path in data_path.iterdir():
        if str(image_path) in values or "mask" not in image_path.name:  # skip mask images
            continue
        try:
            date_str = image_path.name.split('_(')[0].split('_')[0]
            if date_str in wbi_dates:
                wbi = wbi_dates[date_str]
                day_df = day_dfs[date_str]
            else:
                wbi_dates[date_str] = get_wbi(date_str)
                wbi = wbi_dates[date_str]
                df["MESS_DATUM"] = df["MESS_DATUM"].astype(str).str.zfill(12)
                day_df = df[df["MESS_DATUM"].str.startswith(date_str)].copy()
                day_dfs[date_str] = day_df

            time_str = (local_to_utc(image_path.name.split('_(')[0])[:-3] + "0").replace("_", "")
            for i in range(len(day_df)):
                if time_str in str(day_df.iloc[i]["MESS_DATUM"]):
                    temp, rh = (day_df.iloc[i]["TT_10"], day_df.iloc[i]["RF_10"])
                    break
            
            values[str(image_path)] = (wbi, temp, rh, date_str + image_path.name.split('_')[1][:-2])
            del temp, rh
        except Exception as e:
            print(f"Error processing {image_path.name}: {e}")
            continue
    with open(filename_path, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=4)
    

def analyze_all(data_path):
    '''Analyzes all images in data_path, grouped by date. For each date, returns the total number of images, WBI,
       the frequency of images in quarter-hour intervals between sunrise and sunset, frequency of temperatures in 1°C steps between 0°C and 20°C, frequency of relative humidity values in 10%.'''
    data = {}
    for image_path in data_path.iterdir():
        if "mask" not in image_path.name:  # skip mask images
            continue
        try:
            date_str = image_path.name.split('_')[0]
            if date_str not in data:
                single_date_data = analyze_saved_data_time(data_path, date=datetime.strptime(date_str, '%Y%m%d'))
                temps, rhs = frequency_T_RH(*analyze_T_RH(data_path, date_str))

                data[date_str] = {"WBI": get_wbi(date_str), "Total": single_date_data[0], "Time analysis": single_date_data[3], "Temperature frequency": temps, "Relative humidity frequency": rhs}
        except ValueError:
            continue

        total_temps = [0]*20
        total_rhs = [0]*10
        total_after_sunrise = [0]*16
        for date_key, day_data in data.items():
            if date_key == "TOTALS":
                continue
            total_temps = [a + b for a, b in zip(total_temps, day_data["Temperature frequency"])]
            total_rhs = [a + b for a, b in zip(total_rhs, day_data["Relative humidity frequency"])]
            total_after_sunrise = [a + b for a, b in zip(total_after_sunrise, day_data["Time analysis"][:16])]

        total = sum(day_data["Total"] for date_key, day_data in data.items() if date_key != "TOTALS")
        data["TOTALS"] = {"Total": total, "Temperature frequency": total_temps, "Relative humidity frequency": total_rhs, "Time analysis": total_after_sunrise}
    return data


def _as_list(value):
    if isinstance(value, str):
        return ast.literal_eval(value)
    return value

def analyze_new(data_path, filename):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    new_days = []

    for image_path in data_path.iterdir():
        if "mask" not in image_path.name:  # skip mask images
            continue
        try:
            date_str = image_path.name.split('_')[0]
            if date_str not in data or (sum(ast.literal_eval(data[date_str]["Relative humidity frequency"])) == 0 and data[date_str]["Total"] > 0):
                new_days.append(date_str)
                single_date_data = analyze_saved_data_time(data_path, date=datetime.strptime(date_str, '%Y%m%d'))
                temps, rhs = frequency_T_RH(*analyze_T_RH(data_path, date_str))

                data[date_str] = {"WBI": get_wbi(date_str), "Total": single_date_data[0], "Time analysis": single_date_data[3], "Temperature frequency": temps, "Relative humidity frequency": rhs}
        except ValueError:
            continue
    total_temps = [0]*20
    total_rhs = [0]*10
    total_after_sunrise = [0]*16
    for date_key, day_data in data.items():
        if date_key == "TOTALS":
            continue
        elif date_key not in new_days:
            total_temps = list(map(add, total_temps, ast.literal_eval(day_data["Temperature frequency"])))
            total_rhs = list(map(add, total_rhs, ast.literal_eval(day_data["Relative humidity frequency"])))
            total_after_sunrise = list(map(add, total_after_sunrise, _as_list(day_data["Time analysis"])[:16]))
        else:
            total_temps = [a + b for a, b in zip(total_temps, day_data["Temperature frequency"])]
            total_rhs = [a + b for a, b in zip(total_rhs, day_data["Relative humidity frequency"])]
            total_after_sunrise = [a+b for a, b in zip(total_after_sunrise, day_data["Time analysis"][:16])]
        try:
            totals = data["TOTALS"]["Total"]
            totals_t = ast.literal_eval(data["TOTALS"]["Temperature frequency"])
            totals_h = ast.literal_eval(data["TOTALS"]["Relative humidity frequency"])
            totals_time = ast.literal_eval(data["TOTALS"]["Time analysis"])
        except KeyError:
            totals = 0
            totals_t = [0]*20
            totals_h = [0]*10
            totals_time = [0]*16
    data["TOTALS"] = {"Total":sum(total_temps), "Temperature frequency": list(map(add, totals_t, total_temps)), "Relative humidity frequency": list(map(add, totals_h, total_rhs)), "Time analysis": list(map(add,totals_time, total_after_sunrise))}
    return data


def analyze_and_save(input_path):
    if "chimney" in str(input_path).lower():
        if "qwen" in str(input_path).lower():
            filename = "analyzed_data_base_qwen_Chimney.json"
        else:
            filename = "analyzed_data_chimney.json"
    elif "forest" in str(input_path).lower():
        if "qwen" in str(input_path).lower():
            filename = "analyzed_data_base_qwen_Forestfire.json"
        else:
            filename = "analyzed_data_Forestfire.json"
    data = analyze_new(input_path, filename)
    for date_key, day_data in data.items():
        day_data["Temperature frequency"] = str(day_data["Temperature frequency"])
        day_data["Relative humidity frequency"] = str(day_data["Relative humidity frequency"])
        day_data["Time analysis"] = str(day_data["Time analysis"])
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def plot_frequencies(raw_data, start_end_date=None, use_cutoffs = False, plot_type="absFreq"):
    '''Give a plot for the frequency of detections in a temp-humidity plot when cutting of the first 15, 30 ... 120 minutes after sunrise.'''
    import matplotlib.pyplot as plt
    # times from 6:00 to 11:00 in 15 minute intervals for the x-axis in format hhmm
    times=[]
    if plot_type == "absFreq":
        for j in range(500,2200,100):
            times.append(j)
    else:
        for j in range(500,1100,100):
            times.extend(j+i*15 for i in range(4))
    if start_end_date:
        dates = []
        delta = start_end_date[1] - start_end_date[0]   # returns timedelta

        for i in range(delta.days + 1):
            day = start_end_date[0] + timedelta(days=i)
            dates.append(day.strftime("%Y%m%d"))
    print(dates)
    matricies = []
    for i in times:
        temp_humidity_distribution = [[0] * 10 for _ in range(20)]
        for image_path, data in raw_data.items():
            if start_end_date and data[3][:8] not in dates:
                continue
            if use_cutoffs:
                if detection_logic(parameters=data[1:4])[0] == False:
                    continue
            if data[1] >= 20:
                data[1] = 19
            elif data[1] < 0:
                data[1] = 0
            for j in range(10):
                for k in range(20):
                    if plot_type == "absFreq":
                        if k+1 > data[1] >= k and (j+1)*10 > data[2] >= j*10 and (i+100 > int(data[3][-4:]) >= i):
                            temp_humidity_distribution[k][j] += 1
                            print(data)
                    else:
                        if data[1] > k and data[2] <= j*10 and int(data[3][-4:]) >= i:
                            temp_humidity_distribution[k][j] += 1
        matricies.append(temp_humidity_distribution)
    if plot_type == "absFreq":
        total = sum(sum(sum(row) for row in matrix) for matrix in matricies) if matricies else 0
        print(f"Total detections in raw data: {total}")
    global_min = min(min(min(row) for row in matrix) for matrix in matricies) if matricies else 0
    global_max = max(max(max(row) for row in matrix) for matrix in matricies) if matricies else 1

    if plot_type == "absFreq":
        vertical_plots = 3
    else:
        vertical_plots = 2
        matricies = matricies[8:20]
    fig, axs = plt.subplots(vertical_plots, 6, figsize=(18, 10))
    im = None
    for j in range(vertical_plots):
        for k in range(6):
            index = j*6 + k
            if index < len(times):
                im = axs[j][k].imshow(matricies[index], aspect="equal", cmap='hot', vmin=global_min, vmax=global_max/5)
                if plot_type == "absFreq":
                    axs[j][k].set_title(f"{times[index]//100}:{times[index]%100:02d} - ")
                else:
                    axs[j][k].set_title(f"After {times[index]//100+2}:{times[index]%100:02d}")
                axs[j][k].set_xlabel('Humidity (10% steps)')
                axs[j][k].set_ylabel('Temperature (°C)')
                # threshold = (global_min + global_max) / 2
                # for row in range(len(matricies[index])):
                #     for col in range(len(matricies[index][row])):
                #         value = matricies[index][row][col]
                #         text_color = 'white' if value > threshold else 'black'
                #         axs[j][k].text(col, row, f"{value}", ha='center', va='center', color=text_color, fontsize=5)
                axs[j][k].invert_xaxis()
                axs[j][k].invert_yaxis()
    fig.subplots_adjust(right=0.8)
    if im is not None:
        fig.colorbar(im, ax=axs, label='Frequency', fraction=0.02, pad=0.01)
    # plt.tight_layout()
    plt.show()

def update_all():
    data_paths = [
        Path(r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Forestfire\cropped"),
        Path(r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Chimney_cloud_fog_industrial\cropped")
    ]
    for data_path in data_paths:
        analyze_and_save(data_path)
        raw_data_per_image(data_path)


def find_cutoffs(raw_data):
    times=[]
    averages = []
    for j in range(500,1100,100):
        times.append(j)
        averages.append([0,0])
    matricies = []
    n=0
    for i in times:
        temp_humidity_distribution = [[0] * 20 for _ in range(20)]
        for image_path, data in raw_data.items():
            if data[1] >= 20:
                data[1] = 19
            elif data[1] < 0:
                data[1] = 0
            for j in range(20):
                for k in range(20):
                    if k+1 > data[1] >= k and (j+1)*5 > data[2] >= j*5 and (i+100 > int(data[3][-4:]) >= i):
                        temp_humidity_distribution[k][j] += 1
                        averages[n] = (averages[n][0] + data[1], averages[n][1] + data[2])
        matricies.append(temp_humidity_distribution)
        
        averages[n] = (averages[n][0]/sum(sum(row) for row in temp_humidity_distribution), averages[n][1]/sum(sum(row) for row in temp_humidity_distribution))
        n+=1
    print(f"Averages for each time cutoff: {averages}")
    # for each matrix (for each time cutoff), find the optimal combination of temp, humidity and wbi cutoffs that eliminates all detections
    
    optimal_tuples = {}
    n = 0
    for time_cutoff, matrix in zip(times, matricies):
        optimal_tuples[time_cutoff] = []
    #     for submatrix in matrix:
    #         plt.imshow(submatrix, aspect="equal", cmap='hot', vmin=0, vmax=100)
    #         plt.show()
        total_detections = sum(sum(row) for row in matrix)
        if total_detections == 0:
            continue
        optimal_tuples[time_cutoff] = []
        for temp in range(20):
            for rh in range(20):
                detections_over_threshold = 0
                for i in range(temp,20):
                    for j in range(rh+1):
                        detections_over_threshold += matrix[i][j]
                if detections_over_threshold/total_detections < 0.1:
                    if  rh >= 15:
                        optimal_tuples[time_cutoff].append((1 - detections_over_threshold/total_detections, temp, 5*rh, (rh*5-averages[n][1])/averages[n][1] - (temp-averages[n][0])/averages[n][0]))
                    optimal_tuples[time_cutoff].sort(key=lambda x: (x[3]), reverse=True) 
                    optimal_tuples[time_cutoff] = optimal_tuples[time_cutoff][:10]
        if not optimal_tuples[time_cutoff]:
            print(f"No optimal cutoff found for time cutoff {time_cutoff}")
            continue
        n+=1

    for time_cutoff, tuples in optimal_tuples.items():
        print(f"Optimal tuples for time cutoff {time_cutoff}:")
        for tup in tuples:
            print(f"    {tup}")       
                    
        

if __name__ == "__main__":
    data_path = Path(r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Forestfire\cropped")
    data_path = Path(r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Chimney_cloud_fog_industrial\cropped")

    update_all()

    with open("raw_data_Chimney.json", "r") as f:
        raw_data = json.load(f)

    # find_cutoffs(raw_data)

    plot_frequencies(raw_data, start_end_date=(datetime(2026, 5, 1), datetime.now()))

