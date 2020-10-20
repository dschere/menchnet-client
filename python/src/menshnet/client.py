
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
        self.event_handlers = {}

        # user can define custom handlers here for logging
        # and exceptions.
        self.exc_handler = None
        self.log_handler = None
        

    def _mqtt_handler(self, json_msg):
        """ inbound message from running pipeline 

        json_msg {
             event_type: 'log'|'emit'
             args: <dependant on event type>
        }

        "log"  args: (clock_time,severity,msg)
        "emit": args: (key,value) 
        """
        #print("_mqtt_handler %s" % str(json_msg))
        event_type =  json_msg.get('event_type')
        args = json_msg.get('args')
        if event_type == 'emit':
            (key,value) = args 
            handler = self.event_handlers.get(key)
            if handler:
                handler(value)

        # log message from code
        elif event_type == 'log':
            (clock_time_str,severity,msg) = args
            if self.log_handler:
                self.log_handler(args)
            else:     
                logfunc = getattr(self.client.logger,severity) 
                logfunc("%16s %16s %s" % (self.name,clock_time_str,msg))

        # exception thrown in client code, reraise here unless if user
        # has provided an exception handler 
        elif event_type == 'user_code_exception':
            if not self.exc_handler:
                raise RuntimeError("Remote exception from your pipeline %s: %s" % (self.name,args[0]))
            else:
                self.exc_handler(args[0])
     
    def register(self, name, handler):
        self.event_handlers[name] = handler

    def unregister(self, name):
        if name in self.event_handlers:
            del self.event_handlers[name] 

    def stop(self):
        apiKey = self.client.apiKey
        return self.client.m.start(self.resId)


    def start(self, config):
        apiKey = self.client.apiKey
        name = self.name
                      
        topic = "/api/events/%s" % self.resId
        self.client.m.register(topic, self._mqtt_handler)
        
        return self.client.m.start(name, self.resId, topic, config)
        

    def stop(self):
        apiKey = self.client.apiKey
         
        topic = "/%s/events" % self.resId
        self.client.m.unregister(topic)
        return self.client.m.stop(apiKey, self.resId) 
 


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
    url = sys.argv[2]

    def setup_logger():
        fmt = "%(asctime)s %(thread)d %(filename)s:%(lineno)d %(levelname)s\n`"
        fmt += "- %(message)s"
        logging.basicConfig(stream=sys.stdout,
            format=fmt,
            level=logging.DEBUG
        )
    setup_logger()




    mc = Client(apiKey)
    mc.connect()
    p = mc.pipeline('frozen-video-detector')
    
    def on_event(*args):
        print("on event %s" % str(args))

    p.register('frozen-video',on_event)
    # register event 
    # start 
    p.start({
        "url": url,
        "width": 352,
        "height": 240,
        "depth": 1,  
        "interval": 2
    }) 


    time.sleep(60)
    
    p.stop()
         



if __name__ == '__main__':
    unittest()
         
