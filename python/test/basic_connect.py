#!/usr/bin/env python3
"""
both web service and mosquitto are running locally. 

MENSHNET_UNITTEST="yes" is defined

1. simulate the okta routine that creates the api key by calling 
   the same endpoint in the server to generate an apiKey.


"""
import os

os.environ["MENSHNET_UNITTEST"] = "yes"

import menshnet




