"""
sensor module
"""

    
class Sensor(object):
    """
    Represents a server side instance of the the storedClass. 
    """
    def __init__(self, stored_class):
        self.stored_class = stored_class

    def start(self, stored_class, config):
        """
        Start an instance of the stored class on the menshnet cloud 
        """
      
    def stop(self):
        """
        Stop the running instance
        """

    
    def onError(self, error, stack_trace, gmtime_msecs):
        """
        Called in response to a server fault, 

        error: descriptive error message
        stack_trace: list of strings containing a stack trace or none
        gmtime_msecs: system time in milliseconds timezone=greenwich mean time
        """

    def onInfo(self, msg, gmtime_msecs):
        """
        sensor has sent an info message

        msg: user specified text
        gmtime_msecs: system time in milliseconds timezone=greenwich mean time
        """

    def onAlarm(self, data, gmtime_msecs):
        """
        sensor reading is above or below a threshold

        data: user specified data
        gmtime_msecs: system time in milliseconds timezone=greenwich mean time
        """

    def onStat(self, data, gmtime_msecs):
        """
        sensor has sent a statistic 

        data: user specified data
        gmtime_msecs: system time in milliseconds timezone=greenwich mean time
        """
 

