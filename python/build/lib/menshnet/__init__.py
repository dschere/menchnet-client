
import logging
import os
import sys
import time

def createMenshnetLogger(levelname, logfile):
    logger_name = "menshnet"

    # custom logger for client library
    logger = logging.getLogger(logger_name)

    # get as much info as possible for logging
    fmt = "%(asctime)s %(thread)d %(filename)s:%(lineno)d %(levelname)s\n`"
    fmt += "- %(message)s"

    if logfile == '/dev/stdout':
        log_handler = logging.StreamHandler(stream=sys.stdout) 
    else:
        log_handler = logging.handlers.WatchedFileHandler(logfile)
    
    formatter = logging.Formatter(fmt)
    formatter.converter = time.gmtime
    log_handler.setFormatter(formatter)
    logger = logging.getLogger(logger_name)
    logger.addHandler(log_handler)

    level = getattr(logging, levelname.upper())

    logger.setLevel(level)

# create a logger for the library 
createMenshnetLogger( 
    os.environ.get('MENSHNET_LOGLEVEL','info'), 
    os.environ.get('MENSHNET_LOGFILE','/dev/stdout') 
)


from .client import Client

