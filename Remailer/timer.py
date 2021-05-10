import time

class Timer:
    def __init__(self):
        self._start_time = time.monotonic()
        
        
    def startTime(self):
        return self._start_time
    
    def elapsedTime(self):
        now = time.monotonic()
        return now - self._start_time
    
    def simpleElapsedTimeString(self):
        delta = self.elapsedTime()
        
        if delta < 60:
            delta = int(delta)
            return '%ds' % delta
        
        if delta < 3600:
            delta = int(delta / 60)
            return '%dm' % delta
        
        if delta < 86400:
            delta = int(delta / 3600)
            return '%dh' % delta
        
        delta = int(delta / 86400)
        return '%dd' % delta

        
if __name__ == '__main__':
    t = Timer()
    prev_time_str = t.simpleElapsedTimeString()
    
    while True:
        time.sleep(1)
        time_str = t.simpleElapsedTimeString()
        if prev_time_str != time_str:
            print('Elapsed time: ' + time_str)
        prev_time_str = time_str
    
    # d = t.elapsedTime()
    # print("delta = %d" % d)
    #
    # time.sleep(60)
    #
    # d = t.elapsedTime()
    # print("delta = %d" % d)