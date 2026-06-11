import datetime
import os
import time
import threading
from itertools import cycle
from camera_manager import create_cameras_from_configs
from telegram_bot import TelegramBot
from SAM3class import Sam3
from VLMclass import VLM
from check_daytime import is_daytime
from telegram_bot import TelegramBot
from detection_cutoff import detection_logic
from logger_config import LoggerFactory
from healthchecks_monitor import HealthchecksMonitor
from DetectionOrchestrator import DetectionOrchestrator
from config import AppConfig

cfg = AppConfig.load()

# path = r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images"
# path_no_smoke = os.path.join(path, "No_smoke_T=0.5_VLM")
# path_smoke = os.path.join(path, "Smoke_T=0.5_VLM")
# path_A = os.path.join(path_smoke, "Forestfire")
# path_B = os.path.join(path_smoke, "Chimney_cloud_fog_industrial")
# path_C = os.path.join(path_smoke, "unexpected_result")

# image_paths = {
#     "forestfire": path_A,
#     "nonfire": path_B,
#     "uncertain": path_C,
# }

# # create folders if they don't exist
# os.makedirs(path_no_smoke, exist_ok=True)
# os.makedirs(path_A, exist_ok=True)
# os.makedirs(path_B, exist_ok=True)
# os.makedirs(path_C, exist_ok=True)

image_paths = cfg.paths.as_dict()

logger = LoggerFactory.get_logger("detection_app")

healthchecks_uuid = os.getenv("HC_UUID")
healthchecks = HealthchecksMonitor(healthchecks_uuid) if healthchecks_uuid else None

subscribers = cfg.telegram.subscribers
testers = cfg.telegram.testers
BOT_TOKEN = cfg.telegram.bot_token
try:
    telegram_bot = TelegramBot(bot_token=BOT_TOKEN, subscribers=subscribers, testers=testers)
except Exception as e:
    logger.error(f"Failed to initialize Telegram bot: {e}")

telegram_polling_thread = threading.Thread(target=telegram_bot.run_polling, daemon=True)
telegram_polling_thread.start()

if healthchecks:
    healthchecks.install_signal_handlers()
    healthchecks.start()

cam = create_cameras_from_configs(cfg.cameras)[0]

print("Loading sam...")
try:
    sam3 = Sam3(threshold=0.5)
except Exception as e:
    logger.error(f"Failed to initialize SAM3: {e}")

print("Loading vlm...")
try:
    vlm = VLM()
except Exception as e:
    logger.error(f"Failed to initialize VLM: {e}")

detection_orchestrator = DetectionOrchestrator(
    cam=cam,
    sam3=sam3,
    vlm_model=vlm,
    logger=logger,
    image_paths=image_paths,
)
time_interval = cfg.detection.time_interval # seconds between each image capture and analysis

# iterate camera preset positions in a repeating cycle
pos_iter = cycle(cam.preset_positions)

# Retry configuration
max_retries = 3
retry_delay = 5  # seconds, increases exponentially
consecutive_failures = 0
max_consecutive_failures = 5  # Stop after ~2-3 min of failures

try:
    while healthchecks is None or healthchecks.running:
        retry_count = 0
        retry_wait = retry_delay

        while retry_count < max_retries:
            try:
                if is_daytime(49.549495, 11.021824, 'Europe/Berlin'):
                    logger.log_once_per_day("cycle_start", "Starting detection loop.")

                    detection = False
                    start_time = datetime.datetime.now()
                    pos_value = next(pos_iter)
                    
                    detection_result, detection_data = detection_orchestrator.detection_pipeline(pos_value)

                    # detection_result = True    # testing
                    # import torch
                    # detection_data["lowest_point"] = torch.tensor([100, 200])   # testing, needs to be lowest_point = coords[torch.argmax(coords[:, 0])]
                    
                    if detection_result == True:
                        alarm, temp, rh, precipitation = detection_logic()
                        # alarm = True    # testing
                        if alarm:
                            alarm_package = detection_orchestrator.create_alarm_package(detection_data, temp, rh, precipitation)
                            print(f"Alarm package created: {alarm_package}")
                            telegram_bot.register_alert_context(
                                alert_id=alarm_package["alert_id"],
                                timestamp=detection_data["timestamp"],
                                **{k: v for k, v in alarm_package.items() if k != "alert_id"}
                            )
                            if telegram_bot.too_many_alerts_check():
                                send_to_testers_only = True
                            telegram_bot.send_review_sync(
                                cam=cam,
                                alarm_package=alarm_package,
                                send_to_testers_only=send_to_testers_only,
                            )
                        else:
                            non_alarm_log_path = image_paths['forestfire'] / "non_alarm_log.txt"
                            with non_alarm_log_path.open("a", encoding="utf-8") as f:
                                f.write(f"{datetime.datetime.now()}: Detection at Pos. {cam.translate_in_cam_preset(pos_value)} but no alarm triggered (Temp: {temp}°C, RH: {rh}%, Precip: {precipitation}mm)\n")
                        logger.log_detection(cam, alarm, pos_value, temp=temp, rh=rh, precip=precipitation)
                    time.sleep(time_interval)
                    if healthchecks:
                        healthchecks.heartbeat()

                else:
                    logger.log_nighttime_pause()

                    # Success - reset failure counter
                    consecutive_failures = 0
                    break

            except Exception as e:
                retry_count += 1
                logger.error(f"Detection failed (attempt {retry_count}/{max_retries}): {e}", exc_info=True)

                if retry_count < max_retries:
                    logger.info(f"Retrying in {retry_wait}s...")
                    time.sleep(retry_wait)
                    retry_wait = min(retry_wait * 2, 120)  # Exponential backoff, max 120s
                else:
                    consecutive_failures += 1
                    logger.warning(f"Frame failed ({consecutive_failures}/{max_consecutive_failures} consecutive)")

                    if consecutive_failures >= max_consecutive_failures:
                        logger.critical(f"Shutting down due to too many consecutive failures: {e}")
                        import asyncio
                        asyncio.run(telegram_bot.single_broadcast(chat_id=telegram_bot.subscribers[0], caption="Detection shutdown after critical failure. Check logs for details."))
                        if healthchecks:
                            healthchecks.fail()
                        raise SystemExit("Too many consecutive failures")
                    break

        time.sleep(time_interval)
        if healthchecks:
            healthchecks.heartbeat()

except KeyboardInterrupt:
    logger.info("Shutdown requested with Ctrl-C.")
    if healthchecks:
        healthchecks.success()
    raise
finally:
    if healthchecks:
        healthchecks.success()


                    




