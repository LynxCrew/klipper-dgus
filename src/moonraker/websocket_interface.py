import os
import json
from threading import Thread, Lock
from time import sleep
from websocket import WebSocketApp
from jsonmerge import merge


from dgus.display.serialization.json_serializable import JsonSerializable
from globals import CONFIG_DIRECTORY
from moonraker.request_id import WebsocktRequestId

class WebsocketInterface(JsonSerializable):
    ws_app : WebSocketApp
    thread : Thread
    cyclic_query_thread : Thread
    open : bool = False
    printer_ip = "1.2.3.4"
    port = 7125
    json_data_modell = {}
    server_info = {}
    cyclic_query_thread_running = False

    json_resouce_lock = Lock()

    query_req = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "extruder": None,
                "heater_bed": None
            }
        },
        "id": WebsocktRequestId.QUERY_PRINTER_OBJECTS
    }


    subscription_request = {
        "jsonrpc": "2.0",
        "method": "printer.objects.subscribe",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None
            }
        },
        "id": WebsocktRequestId.SUBSCRIBE_REQUEST
    }


    def __init__(self, printer_ip, port) -> None:
        self.printer_ip = printer_ip
        self.port = port
        ws_url = f"ws://{printer_ip}:{str(port)}/websocket?token="
       
        def on_close(ws_app, close_status, close_msg):
            self.ws_on_close(ws_app, close_status, close_msg)

        def on_error(ws_app, error):
            self.ws_on_error(ws_app, error)

        def on_message(ws_app, msg):
            self.ws_on_message(ws_app,msg)

        def on_open(ws_app):
            self.ws_on_open(ws_app)

        self.ws_app = WebSocketApp(
            url=ws_url,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
            on_open=on_open
        )

        #self.load_inital_datamodell()

      
    def load_inital_datamodell(self):
        # we load an initial datamodell that an actual json structure to query from exists
        display_json_file = os.path.join(CONFIG_DIRECTORY, "initial_datamodell.json")

        with open(display_json_file) as json_file:
            json_data = json.load(json_file)
            self.json_data_modell = json_data


    def start(self):
        self.thread = Thread(target=self.ws_app.run_forever)
        self.thread.start()
        self.cyclic_query_thread_running = True
        self.cyclic_query_thread = Thread(target=self.cyclic_query_thread_function)
        self.cyclic_query_thread.start()
        

    def cyclic_query_thread_function(self):
        while self.cyclic_query_thread_running:
            
            if self.open:
            
                query_server_info_json = {
                    "jsonrpc": "2.0",
                    "method": "server.info",
                    "id": WebsocktRequestId.QUERY_SERVER_INFO
                }

                print("send cyclic query...")

            
                self.ws_app.send(json.dumps(query_server_info_json))

            sleep(1)

    
    def stop(self):
        self.cyclic_query_thread_running = False
        self.cyclic_query_thread.join()
        print("Stopped cyclic query thread...")
        
        self.ws_app.close()
        self.thread.join()
        print("Stopped Websocket Communication....")

        
        
        

        
        
    def ws_on_open(self, ws_app):
        self.open = True
        print("Websocket open...")
        self.send_query(ws_app)

    def ws_on_close(self,ws_app, close_status, close_msg):
        self.open = False
        #TODO: Error handling disconnected a.s.o.

    def ws_on_error(self, ws_app, error):
        pass

    def ws_on_message(self, ws_app, msg):
        response = json.loads(msg)
        #print(json.dumps(response, indent=3))
        #global json_data_modell

        if 'id' in response:
            # Response to our query data request 
            if response["id"] == WebsocktRequestId.QUERY_PRINTER_OBJECTS:
                #print(json.dumps(response, indent=2))
                with self.json_resouce_lock:
                    json_merged = merge(self.json_data_modell, response["result"]["status"])
                    self.json_data_modell = json_merged

                print(json.dumps(self.json_data_modell, indent=3))
            
                self.add_subscription(ws_app)

            if response["id"] == WebsocktRequestId.QUERY_SERVER_INFO:
                #print(json.dumps(response, indent=3))
                #self.server_info = response["resut"]
                with self.json_resouce_lock:
                    json_merged = merge(self.json_data_modell["server_info"],response["result"] )
                    self.json_data_modell["server_info"] = json_merged

                    print(json.dumps(response, indent=3))

            if response["id"] == 5555:
                print(json.dumps(response, indent=3))
            
        
        # Subscribed printer objects are send with method: "notifiy_status_update"
        # The subscribed objects are only published when the value has changed.
        # e.g. bed_temperature target set to 50°, extruder temperature has changed, bed_temperature has changed, a.s.o.
        if response['method'] == "notify_status_update":
            print(json.dumps(response, indent=2))
            #TODO: Resource locking - possible data race!
            json_pub_data = response["params"][0]
            json_merged = merge(self.json_data_modell, json_pub_data)
            with self.json_resouce_lock:
                self.json_data_modell = json_merged
            #print(json.dumps(json_merged, indent=2))



    def send_query(self, ws):
       
        self.ws_app.send(json.dumps(self.query_req))

    def unsubscribe_all(self, ws):
        data = {
            "jsonrpc": "2.0",
            "method": "printer.objects.subscribe",
            "params": {
                "objects": { },
            },
            "id": 4654
        }

        self.ws_app.send(json.dumps(data))


    def add_subscription(self, ws):
        self.ws_app.send(json.dumps(self.subscription_request))

    def write_json_config(self):
        websocket_json_config = os.path.join(CONFIG_DIRECTORY, "websocket.json")

        with open(websocket_json_config, "w") as json_file:
            json_file.write(json.dumps(self.to_json(), indent=3))

    def read_json_config(self):
        websocket_json_config = os.path.join(CONFIG_DIRECTORY, "websocket.json")
        with open(websocket_json_config) as json_file:
            json_data = json.load(json_file)
            return self.from_json(json_data)

    def get_klipper_data(self, klipper_data : list, array_index : int = -1):
        with self.json_resouce_lock:
            json_obj = self.json_data_modell
            for dp in klipper_data:
                json_obj = json_obj.get(dp)
                if json_obj is None:
                    print(f"Error Invalid Klipper Data {klipper_data}")
                    return None

            if array_index >= 0:
                json_obj = json_obj[array_index]
            return json_obj


    #JsonSerializable implementation

    def from_json(self, json_data : dict):
        websocket_object = json_data.get("websocket")
        if websocket_object is None:
            print("Malformed Websocket.json: 'websocket' entry is missing!")
            return False
        
        ip_object = websocket_object.get("ip")
        if ip_object is None:
            print("Malformed Websocket.json: Missing 'ip' entry!")
            return False

        port_object = websocket_object.get("port")
        if port_object is None:
            print("Malformed JSON: Missing 'port' entry!")
            return False


        printer_objects_object = websocket_object.get("printer_objects")
        if printer_objects_object is None:
            print("Malformed JSON: Missing 'printer_objects' entry!")
            return False

        data_modell_object = websocket_object.get("data_model")
        if data_modell_object is None:
            print("Malformed JSON: Missing 'data_model' entry!")
            return False

        self.query_req["params"]["objects"] = printer_objects_object
        self.subscription_request["params"]["objects"] = printer_objects_object
        self.json_data_modell = data_modell_object

        self.printer_ip = ip_object
        self.port = port_object

        return True

    def to_json(self):
        websocket_json = {
            "websocket" : {
                "ip" : self.printer_ip,
                "port" : self.port,
                "printer_objects" : self.query_req["params"]["objects"],
                "data_model" : self.json_data_modell
            }
        }

        return websocket_json