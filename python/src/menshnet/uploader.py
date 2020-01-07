"""
Handle the client upload methods
"""

import os
import json
import logging

# logger for this library
logger = logging.getLogger("menshnet")


from .store import StoredClass

def _upload_util(evs, topic, data, _timeout):
    # block until timeout or response. 
    reply = evs.transaction(topic, data,  
            timeout=_timeout
    )
    error = reply.get("error")
    if error:
        return ( error, None )
            
    stored_class = StoredClass(client, sensor_name)
    return ( None, stored_class )


def _upload_filename(client, filename, sensor_name, **kwArgs):
    evs = client.evs
    try:
        code = open(filename).read()
    except:
        raise IOError("unable to open "+filename+" for reading")

    topic = evs.topic_base()+"/upload_filename"
    data = {
        "sensor_name": sensor_name,
        "method": "code",
        "code": code  
    }
    _timeout = kwArgs.get("timeout",15.0)
    return _upload_util(evs, topic, data, _timeout)
    
         
def _upload_git_repo(client, git, sensor_name, **kwArgs):
    evs = client.evs
    try:
        code = open(filename).read()
    except:
        raise IOError("unable to open "+filename+" for reading")

    topic = evs.topic_base()+"/upload_filename"
    data = {
        "sensor_name": sensor_name,
        "method": "git",
        "git": git  
    }
    _timeout = kwArgs.get("timeout",15.0)
    return _upload_util(evs, topic, data, _timeout)
    

def _upload_url(client, url, sensor_name, **kwAargs):
    pass


def Upload(client, **kwArgs):
    """
    Based on kwAargs choose the desired upload method. 
    """
    sensor_name = kwArgs.get('sensor_name')
    if not sensor_name:
        emsg = "'sensor_name' not defined in kwArgs, must"+ \
               " be the name of the class to instantiate"+ \
               " server side for the sensor"
        raise ValueError(emsg)
 
    filename = kwArgs.get('filename')
    if filename:
        return _upload_filename(client, filename, sensor_name, **kwArgs)
        
    git = kwArgs.get('git')
    if git:
        return _upload_git_repo(client, git, sensor_name, **kwArgs)

    url = kwArgs.get('url')
    if url:
        return _upload_url(client, git, sensor_name, **kwArgs)


