#!/usr/bin/env python
"""
Menshnet client module
"""

from .store import StoredClass
from .evtsys import EventSystem    
from .uploader import Upload 




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
        
    def load(self, sensor_name, **kwArgs):
        """
        Load an existing stored class

        sensor_name: Unique name for the class previously uploaded
        kwArgs:
            Optional callback 
                onLoaded, if load(name, onLoaded=callback) is defined
                then load will become an async function and call onLoaded
                when complete. 
        """
        
    def upload(self, **kwArgs):
        """
        Upload a stored class to menshnet

        upload(sensor_name="MySensor",filename="path-to-code-on-host-machine")
        upload(sensor_name="MySensor",url="http[s]://..../path-to-file",module_name="...")
        upload(sensor_name="MySensor",git="git-project-path-to-clone") 


        sensor_name: User chosen identifier that is used to start/stop
                     a sensor and acts as a filter for inbound events.

        If filename is specified:

            filename is a python module that will be uploaded to the server
            for future use. It will be identified on the server by the value of
            sensor_name. See Note #1 below regarding the requirements for 
            this module.

        If git is specified:

            git is the path to a git repo that will be cloned server side.
            
            module_name is the name of a file within the top level path of the
            git repo containing the server side code to be executed. See
            Note #1 below requirments for this module.

        If url is specified:

            url is an http[s] url where to download the user supplied python 
            sensor module. See Note #1 below regarding the requirements for 
            this module.



        Note #1: Sensor module requirements.

        The user supplied sensor module must impliment a register() function.
        This function must return an instance of an object that is derived off
        of one of menshnet's predefined base classes in the server side
        sensor module. Example:


        ```
        from sensors.vp import VideoProcessor

        class MySensor(VideoProcessor):
            def onInit(self, api, cfg):
                "initialization"

            def onImage(self, img):
                "handle each snapshot of video"


        def register():
            return MySensor()

        ```    

        
        # usage:
        c = menshnet.Client()
        (error, stored_class) = c.upload( sensor_name="test", filename="path/to/test.py")

        ```

        

        """
        return Upload(self, **kwArgs)
        


    
        
