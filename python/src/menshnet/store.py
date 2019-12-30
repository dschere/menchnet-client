"""
Manipulation of uploaded code 
"""
import uuid

from .sensor import Sensor

class StoredClass(object):
    """
    Abstracts operations on stored objects that derive off of menshnet's
    base classes. 
    """
    def __init__(self, mclient, class_name):
        self.mclient = mclient
        self.class_name = class_name


    def load(self, name, **kwArgs):
        """
        load state information from an existing storedClass

        load(name) -> load and return sensor object synchronous

        load(name, onLoaded(sensor)) -> load and return sensor async call
        """
        return Sensor(self) 
        

    def save(self, name=None):
        """
        Save state information, associate the uploaded code
        with a user supplied unique name. If name is None
        then a uuid will be generated for the name and it will
        be returned.
        """ 
        if not name:
            name = str(uuid.uuid4())
        
        # use the messenger to save state information for this
        # archive

        return name
    
