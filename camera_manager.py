from VAPIXcamera import VAPIXCamera
from logger_config import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

def create_cameras_from_configs(camera_configs: list) -> list[VAPIXCamera]:
    """Create VAPIXCamera instances from a list of CameraConfig dataclasses."""
    cameras = []
    for i, cam_cfg in enumerate(camera_configs, start=1):
        try:
            cam = VAPIXCamera(
                cam_cfg.ip,
                cam_cfg.username,
                cam_cfg.password,
                cam_no=i,
                preset_positions=cam_cfg.preset_positions,
                preset_map=cam_cfg.preset_map,
                longitude=cam_cfg.longitude,
                latitude=cam_cfg.latitude,
            )
            cameras.append(cam)
        except Exception as e:
            logger.error(f"Failed to initialize camera at {cam_cfg.ip}: {e}")
    return cameras
