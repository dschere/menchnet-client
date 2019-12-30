"""
Handle the client upload methods
"""

import os
import json
import logging

# logger for this library
logger = logging.getLogger("menshnet")


from .store import StoredClass




def _upload_filename(client, filename, class_name, **kwArgs):
    evs = client.evs
    

    try:
        code = open(filename).read()
    except:
        raise IOError("unable to open "+filename+" for reading")

    topic = evs.topic_base()+"/upload_filename"
    data = {
        "class_name": class_name,
        "code": code  
    }

    _response_handler = kwArgs.get("on_uploaded")
    if not callable(_response_handler):
        raise ValueError("on_uploaded must be a function or a callable object")
    _timeout = kwArgs.get("timeout",15.0)

    _error_handler = kwArgs.get("on_error")
    if not callable(_error_handler):
        raise ValueError("on_error must be a function or a callable object")

    def async_handler(data):
        logger.debug("handle server reply to upload")
        reply = json.loads(data.decode())
        if not reply.get('error'):
            stored_class = StoredClass(client, class_name)
            _response_handler(stored_class)
        elif _error_handler:
            _error_handler(reply.get('error')) 
        
    if _response_handler:
        # conduct async transaction
        evs.transaction(topic, data, 
            response_handler=async_handler, 
            timeout=_timeout, 
            error_handler=_error_handler
        )
    else:
        # synchronous mode, block until timeout or response. 
        reply = evs.transaction(topic, data,  
            timeout=_timeout, 
            error_handler=_error_handler
        )
        if _error_handler and reply.get("error"):
            _error_handler(reply.get('error'))
            return 
        stored_class = StoredClass(client, class_name)
        return stored_class
             

    


def Upload(client, **kwArgs):
    """
    Based on kwAargs choose the desired upload method. 
    """
    class_name = kwArgs.get('class_name')
    if not class_name:
        emsg = "'class_name' not defined in kwArgs, must"+ \
               " be the name of the class to instantiate"+ \
               " server side for the sensor"
        raise ValueError()
 
    filename = kwArgs.get('filename')
    if filename:
        return _upload_filename(client, filename, class_name, **kwArgs)
        


