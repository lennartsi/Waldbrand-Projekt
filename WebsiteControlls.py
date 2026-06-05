import json
import time 

def apply_controlls(detection_level: int = 1):
    with open("controlls.json", "r") as f:
        controlls = json.load(f)
    
    stop = controlls["stop_detection"]
    print(f"Detection stopped. Press Start to resume.")
    while stop:
        time.sleep(60)
        with open("controlls.json", "r") as f:
            controlls = json.load(f)
        stop = controlls["stop_detection"]

    pause_until(controlls["pause_detection"])

    new_detection_level = controlls["detection_level"]
    if new_detection_level != detection_level:
        print(f"Detection level changed to {new_detection_level}.")
    
    return new_detection_level

def pause_until(timestring):
    import time
    from datetime import datetime
    target_time = datetime.strptime(timestring, "%Y%m%d%H%M%S")
    seconds_until_target = (target_time - datetime.now()).total_seconds()
    if seconds_until_target > 0:
        print(f"Pausing detection until {target_time}.")
        time.sleep(seconds_until_target)
        print("Resuming detection.")

# def stop_detection(stop: bool):
#     if stop:
#         print("Detection stopped via website.")
#         exit(0)

if __name__ == "__main__":
    pause_until("20260508151200")