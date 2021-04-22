from typing import Callable
import time

TIME_SUPPLIER: Callable[[], float] = time.time


class CkptTimer:
    def __init__(self, time_out: float = None):
        self.stop_time: float = 0
        if time_out is not None:
            self.stop_time = TIME_SUPPLIER() + time_out
        elif not time_out:
            raise ValueError("Time out not set")

    @property
    def remaining_time(self) -> float:
        return max(self.stop_time - TIME_SUPPLIER(), 0)

    def __str__(self):
        return f'{self.remaining_time :.4f} sec'

    def check_remaining_time(self) -> bool:
        return self.remaining_time > 0.0000
