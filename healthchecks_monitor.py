import signal
import sys
from dataclasses import dataclass
from urllib import error, request


@dataclass
class HealthchecksMonitor:
    uuid: str
    timeout: int = 10

    def __post_init__(self):
        self.base_url = f"https://hc-ping.com/{self.uuid}"
        self._running = True
        self._old_sigint = None
        self._old_sigterm = None

    def _ping(self, path: str = "") -> None:
        req = request.Request(self.base_url + path, data=b"", method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout):
                return
        except Exception:
            return

    def start(self) -> None:
        self._ping("/start")

    def heartbeat(self) -> None:
        self._ping("")

    def success(self) -> None:
        self._ping("/0")

    def fail(self) -> None:
        self._ping("/fail")

    def install_signal_handlers(self) -> None:
        self._old_sigint = signal.getsignal(signal.SIGINT)
        self._old_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

    def _shutdown_handler(self, sig, frame):
        self._running = False
        previous_handler = self._old_sigint if sig == signal.SIGINT else self._old_sigterm
        if callable(previous_handler):
            previous_handler(sig, frame)

    @property
    def running(self) -> bool:
        return self._running

    def restore_signal_handlers(self) -> None:
        if self._old_sigint is not None:
            signal.signal(signal.SIGINT, self._old_sigint)
        if self._old_sigterm is not None:
            signal.signal(signal.SIGTERM, self._old_sigterm)

    def notify_crash(self, exc: BaseException) -> None:
        self.fail()
