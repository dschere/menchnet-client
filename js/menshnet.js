/**


...

menshnet = MenshnetClient(apiKey);

menshnet.connect().then(() => {
    var pipeline = menshnet.pipeline( pipeline_name );

    pipeline.register( event_name, (data) => {
        ... handle event ...
    });

    pipeline.log_handler = (nano_time, severity, message) => {
        ... default is to use the console.log ... 
    });

    pipeline.start({ ... });
    ...
    pipeline.stop();


}, (error) = {
    // display error.
});
   



*/

const SETUP_CMD      = "https://menshnet.online/api/setup";
const DISCONNECT_CMD = "https://menshnet.online/api/disconnect";
const START_CMD      = "https://menshnet.online/api/start";
const STOP_CMD       = "https://menshnet.online/api/stop";
const HEARTBEAT_CMD  = "https://menshnet.online/api/heartbeat";

const MENSHNET_ADDR = "menshnet.online";
const MENSHNET_PORT = 9000;

function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

class Messenger {
    function constructor(apiKey) {
        this.apiKey = apiKey        

        // for receiving events only 
        this.mqttc = new Paho.MQTT.Client(MENSHNET_ADDR, MENSHNET_PORT, uuidv4());
        
        // set callback handlers
        this.mqttc.onMessageArrived = this.onMessageArrived;

        // connect the client
        this.mqttc.connect();

        this.handlers = {};
        // default simple minded error handler
        this.service_outage = function(err) {alert(err)}; 
    }

    function register(topic, handler) {
        this.handlers[topic] = handler;
        this.mqttc.subscribe(topic); 
    }

    function unregister(topic) {
        if (typeof this.handlers[topic] !== 'undefined') {
            this.mqttc.unsubscribe(topic);
            delete this.handlers[topic];
        }
    }

    function onMessageArrived(message) {
        var handler = this.handlers[message.topic];
        if (typeof handler !== 'undefined') {
            handler( JSON.parse(message.payloadString) );
        }
    }

    function _json_post(url, data, on_success, on_fail) {
        $.ajax({
            url: url,
            type: 'post',
            dataType: 'json',
            fail: on_fail,
            contentType: 'application/json',
            success: on_success,
            data: JSON.stringify(_data)
        });
    }

    function heartbeat() {
        this._json_post(HEARTBEAT_CMD, { 
            "apiKey": this.apiKey
            }
            () => {},
            () => {}
        ); 
    }

    function stop(resId) {
        this._json_post(STOP_CMD, { 
            "apiKey": this.apiKey,
            "resId": resId
            }
            () => {},
            () => {}
        ); 
    }

    function start(name, resId, event_topic, config, on_success, on_fail) {
        // validate apikey
        this._json_post(START_CMD, {
                "apiKey": this.apiKey,
                "resId": resId,
                "name": name,
                "resId": resId,
                "event_topic": event_topic,
                "config": config
            },  
            on_success, 
            on_fail
        );
    }

    function setup(on_success, on_fail) {
        /*
        Setup communication for receinging events and sending
        commands.    
        */
        
        // validate apikey
        this._json_post(SETUP_CMD, {
                "apiKey": this.apiKey 
            },  
            (data) => {
                var jobj = JSON.parse(data);
                on_success(jobj.result.names);
            },
            (jqXHR, textStatus, errorThrown) => {
                on_fail(parseInt(jqXHR.status) + ": " + jqXHR.statusText);
            }
        );
    }
}


/**
   the pipeline is ment to be created by a factory method called 
   pipeline() in the client. This method is used to:

   * start/stop pipeines
   * route events from menshnet to this client.
*/
class Pipeline
{
    constructor(name, messenger) {
        this.m = messenger;
        this._name = name;
        this.resId = uuidv4();

        // user defined eve
        this.pipeline_event_handlers = {};

        this.log_handler = (clock_time,severity,msg) => {
            console.log(this._name + " " + clock_time + "[" + severity + "]" + msg); 
        });

        this.pipeline_code_exc_handler = (stacktrace) => {
            console.log(this._name + " remote code exception: \n" + stacktrace);
            alert(this._name + " remote code exception: \n" + stacktrace);
        };

        this.event_type_handlers = {
            "log" : (args) => {
                // clock_time_str,severity,msg = args
                this.log_handler(args[0], args[1], args[2]);
            },
            "emit": (args) => {
                // (key,value) = args
                var handler = this.pipeline_event_handlers[ args[0] ];
                if (typeof handler === "function") {
                    handler( args[1] ); 
                }
            }, 
            "user_code_exception": (args) => {
                this.pipeline_code_exc_handler( args[0] );
            }
        };
    }
  
    register(name, handler) {
        this.pipeline_event_handlers[name] = handler;
    }

    unregister(name) {
        if (typeof this.pipeline_event_handlers[name] !== 'undefined') {
            del this.pipeline_event_handlers[name];
        }
    }

    _mqtt_handler( json_msg ) {
        var f = this.event_type_handlers[json_msg.event_type];
        if (typeof f === "function") {
            f(json_msg.args);
        }
    }

    /*
     stop running pipeline
     */
    stop() {
        this.m.stop(this._name);
    }

    /*
     start pipeline
     */
    start(config) {
        var p = new Promise( (resolution,rejection) => {
            var event_topic = "/api/events/" + this.resId;
            //  handle inbound events of all types for this pipeline
            this.m.register(event_topic, this._mqtt_handler);
        
            this.m.start(
                this._name, 
                this.resId, 
                event_topic, 
                config, 
                resolution, 
                rejection 
            );
        });
        return p; 
    }

    
}


class MenshnetClient 
{
    constructor(apiKey) 
    {
        this.pipeline_names = []; 
        this.m = new Messenger(apiKey);
        this.heartbeat_timer = null;
    }

    /* Create a logical connection between this client and menshnet using 
       the apiKey. Return a promise that is fullfuled if the apiKey is valid
       and the operation successful. 
    */
    connect() {
        var client = this;

        var p = new Promise( (resolution,rejection) => {
            this.m.setup((names) = {
                client.pipeline_names = names;
                this.heartbeat_timer = setInterval(()=>{
                    this.m.heartbeat();                    
                }, 15000);
                resolution(); 
            }, rejection);
        });

        return p;
    }

    /*
    factory method that returns a pipeline object.
    */
    pipeline(name) {
        if (this.pipeline_names.indexOf(name) == -1) {
            var "Unknown pipeline '" + name + "' must be one of the following: " 
                + this.pipeline_names;
            throw msg;
        }
        return new Pipeline(name, this.m);
    }

     
}






