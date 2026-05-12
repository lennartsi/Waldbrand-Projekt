import json
import time 

def apply_controlls():
    with open("controlls.json", "r") as f:
        controlls = json.load(f)
    
    stop = controlls["stop_detection"]
    while stop:
        time.sleep(60)
        with open("controlls.json", "r") as f:
            controlls = json.load(f)
        stop = controlls["stop_detection"]

    pause_until(controlls["pause_detection"])


def pause_until(timestring):
    import time
    from datetime import datetime
    target_time = datetime.strptime(timestring, "%Y%m%d%H%M%S")
    print(f"Pausing detection until {target_time}.")
    seconds_until_target = (target_time - datetime.now()).total_seconds()
    if seconds_until_target > 0:
        time.sleep(seconds_until_target)

# def stop_detection(stop: bool):
#     if stop:
#         print("Detection stopped via website.")
#         exit(0)

if __name__ == "__main__":
    pause_until("20260508151200")