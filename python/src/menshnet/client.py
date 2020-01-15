#!/usr/bin/env python
"""
Menshnet client module
"""


from .store import StoredClass
from .evtsys import EventSystem    
from .uploader import Upload 

import logging

Logger = logging.getLogger("menshnet")



class EventHandler(object):
    """
    Capture events from a running sensor on our server
    """

    def on_error(self, errmsg, server_side_stack_trace):
        """
        Capture error message 

        errmsg -> textual message describing error
        server_side_stack_trace -> either a stack trace acquired by calling
                                   traceback.format_exc() which should pinpoint
                                   a fault in code or None if not available. 
        """

    def on_info(self, msg):
        """
        Capture info message

        ```
           In your sensor:
           self.api.send_info("this is a test")
 
           results in this function being called with
           msg == "this is a test"
        ```
        """
        

    def on_stat(self, data):
        """
        Capture server side statistic messages from a sensor.
        
        ```
            def onInit(self, api, cfg):
                self.api = api # save MenshnetApi

            ... later in code send a stat ...
            self.api.send_stat({"ssi":score})

        # receive stat message from your sensor 
        def on_stat(self, data -> {"ssi":score}) 
        ```
        """
        

    def on_alarm(self, name, active, value):
        """
        Capture a server side alarm from your sensor.

        ```
            def onInit(self, api, cfg):
                ... 
                # set an alarm 
                # add(self, name, set_threshold, clear_threshold)
                self.api.alarms.add("frozen-video",self.threshold,self.threshold-0.05)

            # ... then later the alarm is triggered when/if 'score'
            # exceeds set_threshold value=1 and event triggered or
            #  
            self.api.alarms.update("frozen-video",score) 
        ```
        """
         
 
class Sensor(object):
    """ 
    command and control over remote sensor
    """
    def __init__(self, evs, sensor_name, cfg, evt_handler):
        self.evs = evs 
        self.name = sensor_name
        self.cfg = cfg
        self.handler = evt_handler
        self.codeId = None


    def stop(self): 
        "stop reunning sensor, remove inbound event routing"
        if not self.codeId:
            Logger.warning("stop called but sensor does not appear active")
        else:
            topic = self.evs.topic_base()+"/stop_sensor" 
            self.evs.transaction(topic , {
                "codeId": self.codeId
            })
            self.evs.remove_handler(self.codeId)
            

    def start(self):
        """
        start package name <self.name> within the user's git 
        project.
        """
        topic = self.evs.topic_base()+"/start_sensor"
        auth = self.evs.messenger.mqtt_auth
        data = {
            'mqttCred': (auth['name'],auth['pwhash']),
            'name': self.name,
            'cfg' : self.cfg
        }  
        Logger.info("starting sensor %s" % self.name)
        Logger.debug("Sensor.start sending %s" % str(data))
        # start remote service get codeId from server
        # which identfies the instance of the sensor that 
        # is running. 
        r = self.evs.transaction(topic , data)
        if r.get('error'):
            self.handler.on_error(r.get('error'),None)
        else:
            self.codeId = r.get('codeId') 
            self.evs.add_handler(self.codeId, self.handler)

        Logger.debug("Sensor.start sending %s" % str(data))

class Client(object):
    """
    Client communications library, all persistence is done on the remote 
    server.

    Core operations

       register code 
          * a script
          * a git repo
          * an http url
    """
    def __init__(self):
        self.evs = EventSystem()
    
    def connect(self, apiKey, user, **kwArgs):
        """
        Validate apiKey then connect to mqtt for communications.

        apiKey: string obtained by logging into the menshnet site.
        user:   username associated with your menshnet account        

        optional parameters:

            on_connected: a function to be called when connected, if specified
                          connect() becomes asynchronous.
        """
        self.evs.connect(apiKey, user, **kwArgs)
        

    def register(self, gitpath, branch=None):
        """
        register a git repo on menchnet, you may specify an optional branch 
        if not then it will clone the master branch

        gitpath: url of your repo 'git clone <gitpath>'
        branch: if provided a specifc branch 'git -b <branch> <gitpath>'   
        """
        topic = self.evs.messenger.topic_base+"/git_registration" 
        return self.evs.transaction(topic , {
            "gitpath": gitpath,
            "branch": branch  
        })
        
    
    def sensor(self, sensor_name, cfg, evt_handler):
        """
        Return a sensor object that acts as a controller for a remote executing process.
                 
        sensor_name : The name of a python package in your repo:
                     <gitpath you provided in register>/modules/<sensor_name>
        cfg         : A python dictionary containing configuration information
                     obj = <gitpath you provided in register>/modules/<sensor_name>.register()
                     obj.onInit(MenshnetApi, cfg ) <- gets passed to onInit
        evt_handler : Instance of EventHandler which will receive events from sensor
        """
        return Sensor(self.evs, sensor_name, cfg, evt_handler)
    
        
