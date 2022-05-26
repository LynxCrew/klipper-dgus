import json
from dgus.display.communication.communication_interface import SerialCommunication
from controls.moonraker_data_variable import MoonrakerDataVariable
from controls.moonraker_text_variable import MoonrakerTextVariable
from controls.moonraker_printtime_text_variable import MoonrakerPrintTimeTextVariable, PrintTimeDisplay
from dgus.display.mask import Mask

from moonraker.websocket_interface import WebsocketInterface
from controls.klipper_value_format import KlipperValueType

class OverviewDisplayMask(Mask):
    websock : WebsocketInterface = None
    
    temp_extruder = MoonrakerDataVariable
    target_temp_extruder = MoonrakerDataVariable
    temp_bed = MoonrakerDataVariable
    target_temp_bed = MoonrakerDataVariable
    klippy_state = MoonrakerTextVariable
    printer_state = MoonrakerTextVariable
    print_time_total = MoonrakerPrintTimeTextVariable
    print_time_till_finished = MoonrakerPrintTimeTextVariable
    print_completed_percent = MoonrakerDataVariable

    xpos : MoonrakerDataVariable
    ypos : MoonrakerDataVariable

    data = 0
    
    def __init__(self, com_interface: SerialCommunication, websock : WebsocketInterface) -> None:
        super().__init__(0, com_interface)

        self.websock = websock
        
        #0
        self.temp_extruder = MoonrakerDataVariable(self._com_interface, 0x1000, 2, 0xffff, self.websock)
        self.temp_extruder.set_klipper_data([ "extruder", "temperature"])
        self.controls.append(self.temp_extruder)

        #1
        self.target_temp_extruder = MoonrakerDataVariable(self._com_interface, 0x1010, 2, 0xffff, self.websock)
        self.target_temp_extruder.set_klipper_data([ "extruder", "target"])
        self.controls.append(self.target_temp_extruder)

        #2
        self.temp_bed = MoonrakerDataVariable(self._com_interface, 0x1020, 2, 0xffff, self.websock)
        self.temp_bed.set_klipper_data([ "heater_bed", "temperature"])
        self.controls.append(self.temp_bed)

        #3
        self.target_temp_bed = MoonrakerDataVariable(self._com_interface, 0x1030,2, 0xffff, self.websock)
        self.target_temp_bed.set_klipper_data([ "heater_bed", "target"])
        self.controls.append(self.target_temp_bed)

        #4
        self.klippy_state = MoonrakerTextVariable(self._com_interface, 0x1060, 0xffff, 24, self.websock)
        self.klippy_state.set_klipper_data(["server_info", "klippy_state"])
        self.controls.append(self.klippy_state)

        #5
        self.printer_state = MoonrakerTextVariable(self._com_interface, 0x1080, 0xffff, 24, self.websock)
        self.printer_state.set_klipper_data(["print_stats", "state"])
        self.controls.append(self.printer_state)

        #6
        self.print_time_total = MoonrakerPrintTimeTextVariable(self._com_interface, 0x2000, 0xFFFF, 8, self.websock, PrintTimeDisplay.TOTAL_TIME)
        self.controls.append(self.print_time_total)

        #7
        self.print_time_till_finished = MoonrakerPrintTimeTextVariable(self._com_interface, 0x2010, 0xFFFF, 8, self.websock, PrintTimeDisplay.TIME_TILL_FINISH)
        self.controls.append(self.print_time_till_finished)
        
        #8
        self.print_completed_percent = MoonrakerDataVariable(self._com_interface, 0x2020, 2, 0xffff, self.websock, KlipperValueType.PERCENTAGE)
        self.print_completed_percent.set_klipper_data([ "virtual_sdcard", "progress"])
        self.controls.append(self.print_completed_percent)


        self.xpos = MoonrakerDataVariable(self._com_interface, 0x2030, 2, 0xffff, self.websock)
        #self.xpos.set_klipper_data(["toolhead", "position"], 0)
        self.xpos.set_klipper_data(["motion_report", "live_position"], 0)
        self.controls.append(self.xpos)

        self.ypos = MoonrakerDataVariable(self._com_interface, 0x2032, 2, 0xffff, self.websock)
        #self.ypos.set_klipper_data(["toolhead", "position"], 1)
        self.ypos.set_klipper_data(["motion_report", "live_position"], 1)
        self.controls.append(self.ypos)

        self.zpos = MoonrakerDataVariable(self._com_interface, 0x2034, 2, 0xffff, self.websock)
        #self.zpos.set_klipper_data(["toolhead", "position"], 2)
        self.zpos.set_klipper_data(["motion_report", "live_position"], 2)
        self.controls.append(self.zpos)


        # Percent complete ["virtual_sd", "progress"]
        # Print time ["print_stats", "print_duration"]

        self._com_interface.register_spontaneous_callback(0x0010, self.extruder_target_temp_data_changed)
        self._com_interface.register_spontaneous_callback(0x0011, self.bed_target_temp_data_changed)

    def extruder_target_temp_data_changed(self, response : bytes):
        address = int.from_bytes(response[4:6], byteorder='big', signed=False)
        data = response[7:]
                
        temp_str = self.decode_numeric_oskbd_value(data)

        self.send_temperature_cmd("extruder", temp_str)
     

    def bed_target_temp_data_changed(self, response : bytes):
        address = int.from_bytes(response[4:6], byteorder='big', signed=False)
        data = response[7:]
                
        temp_str = self.decode_numeric_oskbd_value(data)

        self.send_temperature_cmd("heater_bed", temp_str)

    def decode_numeric_oskbd_value(self, data : bytes):
        # The data entered with the onscreen keyboard arives ascii coded.
        # And 0xff is appended to terminate the string.
        # But 0xff is not ascii decodable to we just use the data before
        # the first appearance of 0xff
        new_data = bytearray()
        for byte in data:
            if byte != 0xff:
                new_data.append(byte)
            else:
                break

        temperature_str = str(new_data, encoding='ascii')
        temperature_str = temperature_str.replace(",",".")

        return temperature_str


    def send_temperature_cmd(self, heater, temperature):
        if temperature != "":
            if heater != "":
                set_extruder_temp = {
                    "jsonrpc": "2.0",
                    "method": "printer.gcode.script",
                    "params": {
                        "script": f"SET_HEATER_TEMPERATURE HEATER={heater} TARGET={temperature}"
                    },
                    "id": 7466
                }
   
                self.websock.ws_app.send(json.dumps(set_extruder_temp))
