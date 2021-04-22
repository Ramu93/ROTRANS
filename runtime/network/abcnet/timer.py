from typing import Optional, Callable
import time

TIME_SUPPLIER: Callable[[], float] = time.time
"""
Time supplier used in this module to get the current time in seconds.
Can be re-assigned for test purposes.
By default uses the std library function: time.time
"""

class SimpleTimer:
    """
    Can be used to set a timeout and check if the timeout has been reached.
    """
    def __init__(self, time_out: float, start: bool = False, *args, **kwargs):
        """
        Initializes the timer with the given timeout.
        If start is true the timer starts right after the constructor, else the timer object
         already indicates a timeout from the start.

         >>> s = SimpleTimer(5)
         # Initialize timer for 5 second timeout
         >>> s.check()
         # The very first check returns true. The next check would return false.
         True
         >>> s = SimpleTimer(5, start = True)
         >>> s.check()
         False

        :param time_out: Timeout of seconds after which this timer will return true.
        :type time_out: float
        :param start: if true the timer starts after constructor.
        :type start: bool
        :param args: Ignored array args
        :type args: List
        :param kwargs: Ignored dict args
        :type kwargs: Dict
        """
        self.stop_time: float = 0
        self.default_time_out = time_out
        if start:
            self.reset()

    def __get_timeout(self, time_out: Optional[float] = None):
        if time_out is None:
            time_out = self.default_time_out
        if time_out is None:
            raise ValueError("Either set a default time out, or supply a time out.")
        return time_out

    def reset(self, time_out: Optional[float] = None) -> None:
        """
        Resets the timer.

        :param time_out:  If not none, set a new timeout for the next round
        :type time_out: float
        :return: None
        :rtype: None
        """
        time_out = self.__get_timeout(time_out)
        self.stop_time = TIME_SUPPLIER() + time_out

    def check(self) -> bool:
        """
        Checks if the timeout has been reached.
        If a timer with 5 seconds is started, this method will return false up until 5 second pass.
        Then this method will return true

        :return: true if timeout has been reached.
        :rtype: bool
        """
        return self.remaining_time == 0

    @property
    def remaining_time(self) -> float:
        """
        Returns the remaining time left before the timeout has been reached.
        Returns 0, if check returns true.

        :return: time in seconds until timeout will be reached.
        :rtype: float
        """
        return max(self.stop_time - TIME_SUPPLIER(), 0)

    def __str__(self):
        return f'{self.remaining_time :.4f} sec'

    def start_time(self):
        return self.stop_time - self.__get_timeout()

    def run_time(self):
        return TIME_SUPPLIER() - self.start_time()

    def run_time_str(self):
        return f'{self.run_time() :.4f} sec'

    def check_and_set(self, time_out: Optional[float] = None) -> bool:
        """
        Checks if the timeout has been reached.
        If true, the timer will be reset.

        :param time_out: If not none, it will used as the new timer.
        :type time_out: float
        :return: true if the timeout has been reached and the timer was resetted.
        :rtype: bool
        """
        if self.check():
            self.reset(time_out)
            return True
        return False

    def __call__(self, *args, **kwargs) -> bool:
        """
        Calls the ``check_and_set`` method.

        :param time_out: If not none, it will used as the new timer.
        :type time_out: float
        :return: true if the timeout has been reached and the timer was resetted.
        :rtype: bool
        """
        return self.check_and_set()


class StopTimer:
    """
    Timer implementation, that records the time since it was started.
    """

    def __init__(self, start_time: float = None):
        """
        Initializes the timer from zero.
        If start_time is provided, it will be used as a start time, which can be the future or the past.

        :param start_time: if provided it will be used as the start time.
        :type start_time: float
        """
        self._start_time: float = 0
        if start_time:
            self._start_time = start_time
        else:
            self.reset()

    @property
    def start_time(self) -> float:
        """
        Returns the time this stoptimer was started.

        :return: Time this timer was started
        :rtype: float
        """
        return self._start_time

    def reset(self) -> None:
        """
        Resets the timer and sets the starttimer to the current time.
        Calling ``time`` after invoking reset will return almost 0.

        :return: None
        :rtype: None
        """
        self._start_time: float = TIME_SUPPLIER()

    def time(self) -> float:
        """
        Returns the time since timer was started in seconds.

        :return: Time in seconds since this timer was started.
        :rtype: float
        """

        return TIME_SUPPLIER() - self._start_time

    def has_passed(self, time_mark: float) -> bool:
        """
        Returns true if the currect passed time exceeds the given time mark.
        In other words if time() > time_mark
        This method does NOT reset the running time.

        :time_mark: Limit in seconds that is checked to see if the current time is below it.
        :return: True if the given limit is not exceeded by the current passed time.
        """
        if time_mark < 0:
            return False
        if time_mark == 0:
            return True
        return self.time() > time_mark

    def __call__(self, *args, **kwargs) -> float:
        """
        Invoked ``time``.

        :return: Time in seconds since this timer was started.
        :rtype: float
        """
        return self.time()

    def __str__(self) -> str:
        return f'{self.time() :.5f} sec'

