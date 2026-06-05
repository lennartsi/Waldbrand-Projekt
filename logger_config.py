import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import datetime


class ContextualLogger:
    """Wrapper around standard logger with context-aware logging methods."""
    
    def __init__(self, logger):
        self.logger = logger
        self._daily_logged = {}  # Tracks what's been logged today
        
    def _reset_daily_if_needed(self):
        """Reset daily log tracking if we've crossed midnight."""
        today = datetime.date.today()
        if self._daily_logged.get("_date") != today:
            self._daily_logged = {"_date": today}
    
    def log_once_per_day(self, key, message, level="info"):
        """Log a message only once per calendar day."""
        self._reset_daily_if_needed()
        
        if key not in self._daily_logged:
            getattr(self.logger, level)(message)
            self._daily_logged[key] = True
    
    def log_detection(self, cam, alarm, position, temp=None, rh=None, precip=None):
        """
        Log detection depending on alarm status.
        
        Args:
            vlm_result: The VLM output (A=fire, B=non-fire/false positive, None=uncertain)
            position: Camera position number
            image_path: Path where image was saved
            temp/rh/precip: Optional weather data
            is_alarm: Whether alarm was triggered
        """
        position = cam.translate_in_cam_preset(position)
        weather_str = ""
        if temp is not None and rh is not None and precip is not None:
            weather_str = f" (Temp: {temp}°C, RH: {rh}%, Precip: {precip}mm)"
        if alarm:
            self.logger.info(f"Detection at Pos. {position}! {weather_str} - Alarm triggered.")
        else:
            self.logger.info(f"Detection at Pos. {position} but no alarm triggered {weather_str}")
            non_alarm_log_path = cam.image_paths['forestfire'] / "non_alarm_log.txt"
            with non_alarm_log_path.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now()}: Detection at Pos. {position} but no alarm triggered {weather_str}\n")

    
    def log_detection_cycle_start(self):
        """Log detection cycle start - only once per day."""
        self.log_once_per_day(
            "cycle_start",
            "Starting detection loop.",
            level="info"
        )
    
    def log_nighttime_pause(self):
        """Log nighttime pause - only once per day."""
        self.log_once_per_day(
            "nighttime",
            "Currently nighttime. Detection loop paused.",
            level="info"
        )
    
    # Delegate standard logging methods to wrapped logger
    def info(self, msg, *args, **kwargs):
        return self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        return self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        return self.logger.error(msg, *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        return self.logger.debug(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        return self.logger.critical(msg, *args, **kwargs)


class LoggerFactory:
    _configured = False

    @classmethod
    def configure(cls):
        if cls._configured:
            return

        # Primary (network) log directory on NetApp
        net_log_dir = Path(r"\\netappn1\siethoff\Fraunhofer Waldbrand\Camera_test")
        # Local fallback directory (always available)
        local_log_dir = Path.home() / "camera_test_logs"
        local_log_dir.mkdir(parents=True, exist_ok=True)
        # Try to create network directory but don't fail if unavailable
        try:
            net_log_dir.mkdir(parents=True, exist_ok=True)
            network_available = True
        except Exception:
            network_available = False

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        # Local rotating file handler (always enabled)
        local_file_handler = RotatingFileHandler(
            local_log_dir / "detection-logs.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        local_file_handler.setFormatter(formatter)

        # Optional network rotating handler (may fail if NAS is unavailable)
        network_file_handler = None
        if network_available:
            try:
                network_file_handler = RotatingFileHandler(
                    net_log_dir / "detection-logs.log",
                    maxBytes=5 * 1024 * 1024,
                    backupCount=3,
                    encoding="utf-8",
                )
                network_file_handler.setFormatter(formatter)
            except Exception:
                network_file_handler = None

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # Set handler levels
        local_file_handler.setLevel(logging.INFO)
        console_handler.setLevel(logging.INFO)
        if network_file_handler:
            network_file_handler.setLevel(logging.INFO)

        # Attach handlers to the root logger so named loggers inherit them
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(local_file_handler)
        root_logger.addHandler(console_handler)
        # Attach network handler only if it was successfully created
        if network_file_handler:
            root_logger.addHandler(network_file_handler)
        else:
            # If network logging failed, write a startup notice to local log
            root_logger.warning("Network log directory not available; logging to local directory only.")

        # Silence noisy libraries used for model downloads and loading
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("transformers").setLevel(logging.WARNING)
        logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

        cls._configured = True

    @staticmethod
    def get_logger(name: str):
        LoggerFactory.configure()
        return ContextualLogger(logging.getLogger(name))
