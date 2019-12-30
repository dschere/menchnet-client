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
        
    def load(self, name, **kwArgs):
        """
        Load an existing stored class

        name: Unique name for the class previously uploaded
        kwArgs:
            Optional callback 
                onLoaded, if load(name, onLoaded=callback) is defined
                then load will become an async function and call onLoaded
                when complete. 
        """
        
    def upload(self, **kwArgs):
        """
        Upload a stored class to menshnet

        upload(class_name="MySensor",filename="path-to-code")
        upload(class_name="MySensor",url="http[s]://..../path-to-code")
        upload(class_name="MySensor",git="git-project-path-to-clone") 

        To make this function async as opposed to synchronous add the
        onUploaded(error="error message"|None) callback, if error == None
        upload was successful.

        upload(opUploaded=callback, ...)        
        """
        return Upload(self, **kwArgs)
        


    
        
