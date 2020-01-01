"""
Networking module for library, this leverages mqtt and requests
"""

import paho.mqtt.client as mqtt
import queue
import requests
import json
import threading
import uuid
import logging
import os
import sys
import hashlib

REMOTE_HOST="menshnet.online"
VALIDATE_API_URL="https://menshnet.online/landing/api/access-mqtt"

if os.environ.get("MENSHNET_UNITTEST"):
    REMOTE_HOST="localhost"
    VALIDATE_API_URL="http://localhost:20000/api/access-mqtt"


Logger = logging.getLogger("menshnet")


class MqttTransaction(object):
    """
         Sender              MQTT   Receiver
           
         create response
         topic, subscribe ---->|

         subscribed.      <----
         send message     -----+----> process message
                                      send reply to reply
                                      topic
         route response
         end transaction <-----+-----

         unsubscribe to
         response topic  ----->| 

    """
    def __init__(self, messenger, topic, data):
        self.messenger = messenger
        self.topic = topic
        self.data = data
        self.error = None
        self.complete = threading.Event()
        self.reply = None

    # 
    # user defined event handlers
    #
    def on_result(self, mqtt_msg_payload):
        self.reply = mqtt_msg_payload

    def on_success(self):
        pass
        
    def on_failure(self, error):
        Logger.error(error)
    #############################
    


    def wait_for_completion(self, timeout):
        "wait for transaction to complete or timeout"
        Logger.info("waiting for completion")
        if self.complete.wait(timeout):
            if self.error:
                self.on_failure(self.error)
            else:
                self.on_success()
        else:
            self.on_failure("timeout")          

    def on_error(self, msg):
        "route error to on_failure set complete mutex"
        Logger.error("on_error: " + msg)
        self.error = msg         
        self.complete.set()

        # remove if reply topic exists
        if self.data.get('reply_topic'): 
            self.messenger.mqttc.message_callback_remove(self.data['reply_topic'])
            self.messenger.mqttc.unsubscribe(self.data['reply_topic'])

    def reply_handler(self, client, userdata, msg):
        "route inbound message to on_result"
        Logger.debug("received reply from remote service")
        
        self.on_result(msg.payload)
          
        self.messenger.mqttc.message_callback_remove(self.data['reply_topic'])
        self.messenger.mqttc.unsubscribe(self.data['reply_topic']) 

        # unblock and synchronous caller.
        self.complete.set()


    def when_subscribed(self, mid):
        Logger.debug("reply topic has subscribed, sending message")
        # route response reply_topic to reply_handler
        self.messenger.mqttc.message_callback_add(self.data['reply_topic'], self.reply_handler)

        # send to remote host
        self.messenger.send(self.topic, self.data)

        # remove deferred reference.
        if mid in self.messenger.deferred: 
            del self.messenger.deferred[mid]
         

    def begin(self):
        "begin transaction"
        Logger.debug("Beginning transaction")
        

        if not self.messenger.mqttc:
            self.on_error("mqtt not initialized") 
            return

        # reply_topic -> menshnet/client/<username>/tx-reply/<uuid>
        self.data['reply_topic'] = self.messenger.topic_base+"/tx-reply/"+str(uuid.uuid4()) 

        # subscribe to topic
        (sub_result, mid) = self.messenger.mqttc.subscribe(self.data['reply_topic'])
        if sub_result == mqtt.MQTT_ERR_NO_CONN:
            self.on_error("unable to subscribe no connection")
            return

        # defer transaction until subscribed event from mqtt
        self.messenger.deferred[mid] = lambda *args: self.when_subscribed(mid)

        


class Messenger(object):
    def __init__(self):
        self.inbound_msgq = queue.Queue()
        # create a semaphore to block until mqtt connection,
        # the mqtt client will auto reconnect until success.
        self.connected = threading.Event()
        self.connected.clear()     
        self.on_connected = None
        self.mqttc = None
        # functions to be called when subscribed.
        self.deferred = {}
        
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # if provided call user handler when mqtt has connected.
            if self.on_connected:
                self.on_connected()
            # set connected mutex 
            self.connected.set()
       
    def on_subscribe(self, client, userdata, mid, granted_qos):
        "mqtt confirms our subscribe request, call trigger"
        fobj = self.deferred.get(mid)
        if fobj:
            Logger.debug("topic subscribed to, calling deferred function")
            fobj()


    def send(self, topic, data):
        if not self.mqttc:
            raise RuntimeError("connect must be called before using this method")
        self.mqttc.publish(topic,payload=json.dumps(data))
        
    def connect(self, mqtt_auth, on_connected):
        "connect to mqtt using authentication"
        Logger.debug("connecting to mqtt using credentials")
        self.on_connected = on_connected
        self.mqttc = mqtt.Client(transport="websockets")
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_subscribe = self.on_subscribe 
        self.mqttc.tls_set()

        u = mqtt_auth['name']
        p = mqtt_auth['pwhash']

        self.topic_base = "menshnet/user/%s"

        self.mqttc.username_pw_set(u, p)
        self.mqttc.ws_set_options()
        self.mqttc.connect(REMOTE_HOST, 443, 60)

        # execute daemon thread for network communications to the
        # MQTT broker 
        self.mqttc.loop_start()


class EventSystem(object):
    """
    Wrapper aroung MQTT for messaging.
    """
    def __init__(self):
        self.messenger = Messenger()
        
    def topic_base(self):
        "return base topic path allocated for this user: menshnet/client/<username>/#"
        if self.messenger.connected.is_set():
            return self.messenger.topic_base

    def transaction(self, topic, data, response_handler=None, timeout=15.0, error_handler=None):
        """
        Handle a transaction either in synchronous mode (blocking) or async. For async
        response must be a callable object. 
        """
        
        tx = MqttTransaction(self.messenger, topic, data)

        # set error handler, default is to just scream at the error log ;)
        if error_handler:
            tx.on_failure = error_handler
        
        if response_handler:
            tx.on_response = response_handler
        
        tx.begin()
        if not response_handler:
            
            tx.wait_for_completion(timeout)

        # reply will be none if in async mode (response_handler == None)
        return tx.reply 



    def connect(self, apiKey, user, **kwArgs):
        """
        Authenticate apiKey, enable mqtt communications to topics then
        connect to mqtt.        
        """

        on_connected = kwArgs.get('on_connected')
        if on_connected and not callable(on_connected):
            raise ValueError("When specified on_connected must be a callable object/function")

        if os.environ.get("MENSHNET_UNITTEST","no") == "yes":
            class Fake_response:
                 def __init__(self):
                     u = os.environ["MENSHNET_UNITTEST_MQTT_USERNAME"].encode('utf-8')
                     self.content = json.dumps({
                         "name": hashlib.md5(u).hexdigest(),
                         "pwhash": os.environ["MENSHNET_UNITTEST_MQTT_PWHASH"]
                     }).encode('utf-8')
                     self.status_code = 200
            r = Fake_response()
            print("Unit test mode: %s" % str(vars(r)))
        else:
            r = requests.post(VALIDATE_API_URL, json={
                "apiKey": apiKey,
                "user": user
            })

        if r.status_code == 403:
            raise PermissionError(apiKey)
       
        elif r.status_code == 200:
            # validated, get the mqtt authentication information
            mqtt_auth = json.loads(r.content.decode())
            self.messenger.connect(mqtt_auth, on_connected)
            if not on_connected:
                # synchronous mode, block until connected.
                self.messenger.connected.wait()
        else:
            raise RuntimeError("HTTP %d Error while validating apiKey '%s'" % (r.status_code,r.content))
                  

class UnitTest(object):
    """
    Perform unit tests.
    """
    def __init__(self):
        pass
    def run(self):
        es = EventSystem()
        # connect synchronously 
        es.connect("dummy","unittest")
        print("connected")


if __name__ == '__main__':
    UnitTest().run()







     



