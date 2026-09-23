import time
from threading import Semaphore

class RateLimiter:
    """Gioi han so request/phut, tu dong cho neu vuot"""
    def __init__(self, max_per_minute=180):  # de du 5 request duoi nguong 40
        self.max_per_minute = max_per_minute
        self.min_interval = 60.0 / max_per_minute
        self.last_call = 0

    def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()