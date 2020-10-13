
import logging
import threading
import requests
import time
import uuid

try:
    from .messenger import Messenger
except:
    from messenger import Messenger

class NotAuthorizedError(RuntimeError):
    pass


class Pipeline(object):
    def __init__(self, name, client):
        self.client = client
        self.name = name
        self.resId = str(uuid.uuid4())

    def register(self, eventName, eventHandler):
        """
        register used specified event handler. The content of
        the message is at the descretion of the user.
        """
        self.client.m.register(eventName, eventHandler)

    def unregister(self, eventName, eventHandler):
        """
        unregister event handler
        """    
        self.client.unregister(eventName)

    def start(self, config):
        # "/events/%s" % self.resId
        # start(self, apiKey, name, resId, config)
        apiKey = self.client.apiKey
        name = self.name
          

    def stop(self):
        pass
 


class Client(object):
    """
    menshnet client, see the menshnet-client-template and online tutorail for
    how to setup your computer vision pipelines.

    Usage:
    ```
    import menshnet

    mclient = menshnet.Client(apiKey)
    mclient.connect()
    pipeline = mclient.pipeline("name as specifed in yaml file")
    pipeline.register("event name", handler)
    pipeline.start()
    ...
    pipeline.stop()
 
    ```

    """     
    def __init__(self, apiKey, **kwargs):
        if 'logger' in kwargs:
            self.logger = kwargs['logger']
        else:
            self.logger = logging
        self.apiKey = apiKey
        self.m = Messenger(self.apiKey, self.logger)
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_thread)
        self.heartbeat_thread.daemon = True 
        self.pipeline_names = []

    def _heartbeat_thread(self):
        while True:
            self.m.heartbeat()
            time.sleep(15)

    def pipeline(self, name):
        """ 
        check to see if pipeline name exists, return an object dedicated
        to handling events from the pipeline.
        """
        if name not in self.pipeline_names:
            f = "No pipeline named %s, must be one of %s"
            raise ValueError(f % (name,",".join(self.pipeline_names)))
        return Pipeline(name, self)
         

    def connect(self, timeout=15):
        """
        Perform:
        1. Authenticate the apiKey 
        2. Preload git repo meta data
        3. start a background thread to send heartbeat messages.    
        """ 
        self.pipeline_names = self.m.setup(timeout=timeout)
        self.heartbeat_thread.start()
        

def unittest():
    import sys
    import logging


    apiKey = sys.argv[1]
    logging.basicConfig(stream=sys.stdout,level=logging.DEBUG,format="%(message)s")    


    mc = Client(apiKey)
    mc.connect()
    p = mc.pipeline('frozen-video-detector')
    
    def on_event(*args):
        print("on event %s" % str(args))

    p.register('frozen-video',on_event)
    # register event 
    # start 
    time.sleep(30)
    
         



if __name__ == '__main__':
    unittest()
         
