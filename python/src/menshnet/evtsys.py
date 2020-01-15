"""
Networking module for library, this leverages mqtt and requests
"""

import queue
import requests
import json
import threading
import uuid
import os
import sys
import time

import paho.mqtt.client as mqtt


REMOTE_HOST="menshnet.online"
VALIDATE_API_URL="https://menshnet.online/landing/api/access-mqtt"
SUBSCRIBE_TIMEOUT = 15.0
HEARTBEAT_INTERVAL = 15.0

import logging
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
        assert type(data) == type({})
        self.messenger = messenger
        self.topic = topic
        self.data = data
        self.complete = threading.Event()
        self.reply = {"error": "Internal error"}

    # 
    # user defined event handlers
    #
    def on_result(self, mqtt_msg_payload):
        #self.reply = mqtt_msg_payload
        self.reply = json.loads(mqtt_msg_payload.decode())
        

    def on_success(self):
        pass
        
    def on_failure(self, error):
        Logger.error(error)
    #############################
    
    
    def _on_result(self, mqtt_msg_payload):
        self.reply = json.loads(mqtt_msg_payload.decode())


    def wait_for_completion(self, timeout):
        "wait for transaction to complete or timeout"
        Logger.info("waiting for completion")
        if not self.complete.wait(timeout):
            self.on_error("timeout")          

    def on_error(self, msg):
        "route error to on_failure set complete mutex"
        Logger.error("on_error: " + msg)
        self.reply = {"error": msg}         
        self.complete.set()

        # remove if reply topic exists
        if self.data.get('reply_topic'): 
            self.messenger.mqttc.message_callback_remove(self.data['reply_topic'])
            self.messenger.mqttc.unsubscribe(self.data['reply_topic'])

    def reply_handler(self, client, userdata, msg):
        "route inbound message to on_result"
        Logger.debug("received reply from remote service")
        
        self._on_result(msg.payload)
          
        self.messenger.mqttc.message_callback_remove(self.data['reply_topic'])
        self.messenger.mqttc.unsubscribe(self.data['reply_topic']) 

        # unblock and synchronous caller.
        self.complete.set()

    def begin(self):
        "begin transaction"
        Logger.debug("Beginning transaction")
        
        if not self.messenger.mqttc:
            self.on_error("mqtt not initialized") 
            return

        # reply_topic -> menshnet/client/<username>/tx-reply/<uuid>
        self.data['reply_topic'] = self.messenger.topic_base+"/tx-reply/"+str(uuid.uuid4()) 

        # subscribe to topic
        timeout = self.messenger.subscribe(self.data['reply_topic'])
        if timeout:
            self.on_error("timeout")
            return

        self.messenger.mqttc.message_callback_add(self.data['reply_topic'], self.reply_handler)
        # send to remote host
        
        self.messenger.send(self.topic, self.data)

    
class _SyncSubscribe:
    def __init__(self):
        self.pending = {}
        
    def subscribe(self, mqtt_client, topic):
        if not mqtt_client:
            raise RuntimeError("no mqtt client, was connect even called?")

        (result,mid) = mqtt_client.subscribe(topic)
        if result == mqtt.MQTT_ERR_NO_CONN:
            raise RuntimeError("trying to subscribe to %s but not connected!" % topic) 

        self.pending[mid] = threading.Event() 
        Logger.debug("subscription request for topic=%s mid=%d" % (topic,mid))
        # wait until timeout, return true is timeout
        return not self.pending[mid].wait(SUBSCRIBE_TIMEOUT)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        lock = self.pending.get(mid)
        if lock:
            Logger.debug("subscription for mid=%d confirmed" % mid)
            lock.set()


class EventRouter(object):
    """
    Capture events from the backend MenshnetApi object 
    """
    def __init__(self):
        self.handlers = {}

    def add(self, codeId, handler):
        self.handlers[codeId] = handler

    def remove(self, codeId): 
        del self.handlers[codeId]

    def alarm_handler(self, client, userdata, msg):
        jobj = json.loads(msg.payload.decode())
        codeId = jobj.get('codeId')
        h = self.handlers.get(codeId)
        if h and getattr(h,'on_alarm') and callable(h.on_alarm):
            data = jobj['data']
            h.on_alarm(data['name'], data['active'], data['value'])
        else:
            Logger.warning("alarm codeId=%s data=%s" % (codeId,str(jobj['data'])))

    def stat_handler(self, client, userdata, msg):
        jobj = json.loads(msg.payload.decode())
        codeId = jobj.get('codeId')
        h = self.handlers.get(codeId)
        if h and getattr(h,'on_stat') and callable(h.on_stat):
            h.on_alarm(jobj['data'])
        else:
            Logger.info("stat %s" % str(jobj))

    def error_handler(self, client, userdata, msg):
        jobj = json.loads(msg.payload.decode())
        codeId = jobj.get('codeId')
        h = self.handlers.get(codeId)
        if h and getattr(h,'on_error') and callable(h.on_error):
            h.on_error(jobj['error'], jobj.get('stacktrace'))
        else:
            Logger.error("error %s" % str(jobj))
    
    def info_handler(self, client, userdata, msg):
        jobj = json.loads(msg.payload.decode())
        codeId = jobj.get('codeId')
        h = self.handlers.get(codeId)
        if h and getattr(h,'on_info') and callable(h.on_info):
            h.on_info(jobj['msg'])
        else:
            Logger.info("info %s" % str(jobj))


    def setup(self, topic_base, mqttc):
        self.mqttc = mqttc
        self.topic_base = topic_base

        self.topic_routes = {
            topic_base+"/alarm": self.alarm_handler,
            topic_base+"/stat": self.stat_handler,
            topic_base+"/error": self.error_handler,
            topic_base+"/info": self.info_handler
        }
        for t, h in self.topic_routes.items(): 
            self.mqttc.message_callback_add(t,h)

    def codeIdList(self):
        return self.handlers.keys() 


class Messenger(object):
    def __init__(self, user):
        self.user = user
        self.topic_base = "menshnet/client/%s" % self.user
        # create a semaphore to block until mqtt connection,
        # the mqtt client will auto reconnect until success.
        self.connected = threading.Event()
        self.connected.clear()     
        self.on_connected = None
        self.mqttc = None
        self.mqtt_auth = None
        self.sync_sub = _SyncSubscribe()
        
        self.event_router = EventRouter()
        self.hb_thread = threading.Thread(target=self._heartbeat,daemon=True)
        self.hb_thread.start()

    def _heartbeat(self):
        """
        send periodic heartbeat messages to keep sensors alive. This is done for two reasons
        as opposed to a last will message. First the client may be alive but not responive
        so that it is in effect *dead* also the javascript version of the mqtt client does
        not issue a last will message consitently. 
        """
        while True:
            data  = {
                "codeIdList": self.event_router.codeIdList()
            }
            if len(data["codeIdList"]) > 0: 
                topic = self.topic_base+"/heartbeat"
                self.send(topic, data)
                time.sleep(HEARTBEAT_INTERVAL)    
    

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # if provided call user handler when mqtt has connected.
            if self.on_connected:
                self.on_connected()
            # set connected mutex 
            self.connected.set()
            self.event_router.setup(self.topic_base, client)

    def subscribe(self, topic):
        self.sync_sub.subscribe(self.mqttc, topic) 


    def send(self, topic, data):
        if not self.mqttc:
            raise RuntimeError("connect must be called before using this method")
        Logger.debug("mqttc.publish('%s',payload='%s')" % (topic,str(data)))
        self.mqttc.publish(topic,payload=json.dumps(data))

    def on_message(self, client, userdata, msg):
        Logger.debug(msg.topic + " -> " + msg.payload.decode() )
        
    def connect(self, mqtt_auth, on_connected):
        "connect to mqtt using authentication"
        Logger.debug("connecting to mqtt using credentials")
        self.on_connected = on_connected
        self.mqttc = mqtt.Client(client_id=str(uuid.uuid4()), transport="websockets")
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message
        self.mqttc.on_subscribe = self.sync_sub.on_subscribe
        self.mqttc.tls_set()
        
        u = mqtt_auth['name']
        p = mqtt_auth['pwhash']

        self.mqtt_auth = mqtt_auth 

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
        self.messenger = None
        
    def topic_base(self):
        "return base topic path allocated for this user: menshnet/client/<username>/#"
        if self.messenger and self.messenger.connected.is_set():
            return self.messenger.topic_base
        else:
            raise RuntimeError("Attempt to get topic base while not connected.")

    def add_handler(self, codeId, evtHandler):
        "route events based on a codeId"
        if self.messenger and self.messenger.connected.is_set():        
            self.messenger.event_router.add(codeId, evtHandler)
        else:
            raise RuntimeError("Attempt to add event handler while not connected")
     
    def remove_handler(self, codeId):
        "remove codeId from routing"
        if self.messenger and self.messenger.connected.is_set():        
            self.messenger.event_router.remove(codeId)
        

    def transaction(self, topic, data, timeout=15.0):
        """
        Handle a transaction either in synchronous mode (blocking) or async. For async
        response must be a callable object. 
        """
        tx = MqttTransaction(self.messenger, topic, data)

        tx.begin()
        tx.wait_for_completion(timeout)

        # return a dictionary, tx.reply['error'] != None if an error occured.
        return tx.reply 



    def connect(self, apiKey, user, **kwArgs):
        """
        Authenticate apiKey, enable mqtt communications to topics then
        connect to mqtt.        
        """
        self.messenger = Messenger(user)

        on_connected = kwArgs.get('on_connected')
        if on_connected and not callable(on_connected):
            raise ValueError("When specified on_connected must be a callable object/function")

        if os.environ.get("MENSHNET_UNITTEST","no") == "yes":
            class Fake_response:
                 def __init__(self):
                     self.content = json.dumps({
                         "name": os.environ["MENSHNET_UNITTEST_MQTT_USERNAME"],
                         "pwhash": os.environ["MENSHNET_UNITTEST_MQTT_PWHASH"]
                     }).encode('utf-8')
                     self.status_code = 200
            r = Fake_response()
            Logger.debug("Unit test mode: %s" % str(vars(r)))
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

    def fake_tx_server(self, es):
        print("fake_tx_server")
        lock = threading.Event()
        def echo_reply(client, userdata, message):
            print("received message")
            data = message.payload.decode()
            m = json.loads(data)
            print("publish reply to %s" % m['reply_topic'])
            client.publish(m['reply_topic'],payload=json.dumps(m))
            print('fake_tx_server unlock')
            lock.set()
        print("subscribed to %s" % es.messenger.topic_base+"/echo")
        es.messenger.subscribe(es.messenger.topic_base+"/echo")
        es.messenger.mqttc.message_callback_add(es.messenger.topic_base+"/echo",echo_reply) 
        lock.wait() 
        import time
        # wait for message to be published before exiting
        time.sleep(2)

    def fake_tx_client(self, es):
        r = es.transaction( es.messenger.topic_base+"/echo", {'hello':'world'})
        print("response " + str(r))

    def run(self):
        es = EventSystem()
        # connect synchronously 
        es.connect("dummy",os.environ["MENSHNET_UNITTEST_MQTT_USERNAME"])
        print("connected")
        cmd = sys.argv[1]
        method = getattr(self,cmd)
        method(es)        


if __name__ == '__main__':
    UnitTest().run()







     



