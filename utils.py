import datetime
import json
import os
import datetime
import argparse
import sys
from pathlib import Path

import os

from aravis import Aravis

PREFIX_NAME0 = "sensor_0-"
PREFIX_NAME1 = "sensor_1-"

IPAD_X = 10
IPAD_Y = 10

pfnc = {
    "Mono8": {"value": 0x01080001, "depth": 8, "dim": 2},
    "Mono10": {"value": 0x01100003, "depth": 10, "dim": 2},
    "Mono12": {"value": 0x01100005, "depth": 12, "dim": 2},
    "Mono16": {"value": 0x01100009, "depth": 16, "dim": 2},
    "BayerBG8": {"value": 0x0108000B, "depth": 8, "dim": 2},
    "BayerBG10": {"value": 0x0110000F, "depth": 10, "dim": 2},
    "BayerBG12": {"value": 0x01100013, "depth": 12, "dim": 2},
    "BayerRG8": {"value": 0x0108000B, "depth": 8, "dim": 2},
    "BayerRG10": {"value": 0x0110000F, "depth": 10, "dim": 2},
    "BayerRG12": {"value": 0x01100013, "depth": 12, "dim": 2},
}


def switchFontColor(color_mode, current_color=None):
    if color_mode:
        return (255, 255, 255) if current_color == (0, 0, 0) else (0, 0, 0)
    else:
        return (65535, 65535, 65535) if current_color == (0, 0, 0) else (0, 0, 0)


def set_commandline_options():
    parser = argparse.ArgumentParser(description="U3V Camera")
    parser.add_argument('-d', '--directory', default='./output', type=str, help='Directory to save log')
    parser.add_argument('-g', '--gain-key-name', default='Gain', type=str,
                        help='Name of Gain key defined for GenICam feature')
    parser.add_argument('-e', '--exposuretime-key-name', default='ExposureTime', type=str,
                        help='Name of ExposureTime key defined for GenICam feature')
    parser.add_argument('-nd', '--number-of-device', default=2, type=int,
                        help='The number of devices')
    parser.add_argument('-rt', '--realtime-display-mode', action=argparse.BooleanOptionalAction, default=True,
                        help='Switch image capture mode(realtime)')
    parser.add_argument('-sync', '--frame-sync-mode', action=argparse.BooleanOptionalAction, default=False,
                        help='Switch image capture mode{synchronized}')
    parser.add_argument('--sim-mode', default=False, type=bool)
    parser.add_argument('--pixel-format', default='Mono8', type=str,
                        help='valid only --color-display-mode is active')

    return parser


def log_write(logtype, msg):
    print("[LOG {0}][{1}] {2}".format(Path(__file__).name, logtype, msg))


# get device info ##############################################################
def get_device_info(parser, load_json_path="default.json"):
    load_json = False
    if os.path.isfile(load_json_path):
        with open(load_json_path, 'r') as f:
            setting_config = json.load(f)
        load_json = True

    dev_info = {}
    test_info = {}

    # get user input
    args = parser.parse_args()
    SIMULATION = False
    if args.sim_mode:
        SIMULATION = True
    if SIMULATION:
        test_info["Simulation Mode"] = SIMULATION
        test_info["Default Directory"] = args.directory
        if not os.path.isdir(test_info["Default Directory"]):
            os.mkdir(test_info["Default Directory"])
        dev_info["Number of Devices"] = 2
        dev_info["Width"] = 640
        dev_info["Height"] = 480

        dev_info["PixelFormat"] = args.pixel_format
        dev_info["PayloadSize"] = [dev_info["Width"] * dev_info["Height"] * required_bit_depth(
            dev_info["PixelFormat"]) // 8] * dev_info["Number of Devices"]
        dev_info["FrameRate"] = 25
        dev_info["Gain Min"] = 0
        dev_info["Gain Max"] = 100
        dev_info["Gain Key"] = "Gain"
        dev_info[dev_info["Gain Key"]] = setting_config["gains"] if load_json else [40] * dev_info["Number of Devices"]
        dev_info["ExposureTime Min"] = 1
        dev_info["ExposureTime Max"] = 1.0 / dev_info["FrameRate"] * 1000 * 1000
        dev_info["ExposureTime Key"] = "ExposureTimeAbs"
        dev_info[dev_info["ExposureTime Key"]] = setting_config["exposuretimes"] if load_json else [100] * dev_info[
            "Number of Devices"]

        if dev_info["PixelFormat"].startswith("Bayer"):
            test_info["Color Display Mode"] = True
            if dev_info["PixelFormat"].startswith("BayerBG"):
                test_info["Color Pattern"] = "BGGR"
            elif dev_info["PixelFormat"].startswith("BayerRG"):
                test_info["Color Pattern"] = "RGGB"
        else:
            test_info["Color Display Mode"] = False
        dev_info["DeviceModelNames"] = []
        for i in range(dev_info["Number of Devices"]):
            dev_info["DeviceModelNames"].append("fake-" + str(i))

    else:
        test_info["Simulation Mode"] = SIMULATION
        test_info["Default Directory"] = args.directory
        if not os.path.isdir(test_info["Default Directory"]):
            os.mkdir(test_info["Default Directory"])

        test_info["Realtime Display Mode"] = args.realtime_display_mode
        test_info["Frame Sync Mode"] = args.frame_sync_mode
        dev_info["Gain Key"] = args.gain_key_name
        dev_info["ExposureTime Key"] = args.exposuretime_key_name
        dev_info["Number of Devices"] = args.number_of_device

        # Access to the device
        devices = []
        Aravis.update_device_list()
        connected_num_device = Aravis.get_n_devices()
        if connected_num_device == 0:
            Aravis.shutdown()
            raise Exception("No device was found.")
        log_write("INFO", "Device number : {} ".format(connected_num_device))
        first_camera = Aravis.get_device_id(0)
        dev_info["DeviceModelNames"] = []
        dev_info["DeviceModelNames"].append(first_camera)
        if connected_num_device == 2:
            second_camera = Aravis.get_device_id(1)
            dev_info["DeviceModelNames"].append(second_camera)

        devices.append(Aravis.Camera.new(first_camera).get_device())

        if devices[0].is_feature_available("OperationMode"):
            dev_info["OperationMode"] = devices[0].get_string_feature_value("OperationMode")
            expected_num_device = 1 if "Came1" in dev_info["OperationMode"] else 2
            if expected_num_device != dev_info["Number of Devices"]:
                log_write("INFO",
                          f"While OperationMode is set to {dev_info['OperationMode']}, Number of Devices is set to {dev_info['Number of Devices']} (Default: 1)")

                dev_info["Number of Devices"] = expected_num_device

        if dev_info["Number of Devices"] == 2:
            devices.append(Aravis.Camera.new(Aravis.get_device_id(1)).get_device())

        dev_info["GenDCStreamingMode"] = False
        if devices[0].is_feature_available("GenDCDescriptor") and devices[0].is_feature_available("GenDCStreamingMode"):
            if devices[0].get_string_feature_value("GenDCStreamingMode"):
                dev_info["GenDCStreamingMode"] = True

        dev_info["Width"] = devices[0].get_integer_feature_value("Width")
        dev_info["Height"] = devices[0].get_integer_feature_value("Height")
        dev_info["PixelFormat"] = devices[0].get_string_feature_value("PixelFormat")
        try:
            dev_info["FrameRate"] = devices[0].get_float_feature_value("AcquisitionFrameRate")
        except:
            dev_info["FrameRate"] = 30  # how to get the framerate for kizashi 1.0?
        if dev_info["PixelFormat"] not in pfnc:
            log_write("ERROR", "{} is currently not supported on calibration tool".format(dev_info["PixelFormat"]))
            del devices[0]
            Aravis.shutdown()
            sys.exit(1)

        if dev_info["PixelFormat"].startswith("Bayer"):
            test_info["Color Display Mode"] = True
            if dev_info["PixelFormat"].startswith("BayerBG"):
                test_info["Color Pattern"] = "BGGR"
            elif dev_info["PixelFormat"].startswith("BayerRG"):
                test_info["Color Pattern"] = "RGGB"
        else:
            test_info["Color Display Mode"] = False

        for k in ["Gain Key", "ExposureTime Key"]:
            if not devices[0].is_feature_available(dev_info[k]):
                parser.print_help(sys.stderr)
                raise Exception("{0} is an invalid feature key to access {1}".format(dev_info[k], k))

        try:
            dev_info["Gain Min"] = devices[0].get_float_feature_bounds(dev_info["Gain Key"])[0]
            dev_info["Gain Max"] = devices[0].get_float_feature_bounds(dev_info["Gain Key"])[1]
            # calculated
            dev_info["ExposureTime Min"] = 1.0
            dev_info["ExposureTime Max"] = 1.0 / dev_info["FrameRate"] * 1000 * 1000

        except:
            dev_info["Gain Min"] = float(devices[0].get_integer_feature_bounds(dev_info["Gain Key"])[0])
            dev_info["Gain Max"] = float(devices[0].get_integer_feature_bounds(dev_info["Gain Key"])[1])
            # calculated
            dev_info["ExposureTime Min"] = 1.0
            dev_info["ExposureTime Max"] = 1.0 / dev_info["FrameRate"] * 1000 * 1000

        dev_info["PayloadSize"] = []
        for i in range(dev_info["Number of Devices"]):
            dev_info["PayloadSize"].append(devices[i].get_integer_feature_value("PayloadSize"))

        dev_info[dev_info["Gain Key"]] = []
        dev_info[dev_info["ExposureTime Key"]] = []

        if load_json:
            dev_info[dev_info["Gain Key"]] = setting_config["gains"]
            dev_info[dev_info["ExposureTime Key"]] = setting_config["exposuretimes"]

        else:
            for i in range(dev_info["Number of Devices"]):
                try:
                    dev_info[dev_info["Gain Key"]].append(devices[i].get_float_feature_value(dev_info["Gain Key"]))
                    dev_info[dev_info["ExposureTime Key"]].append(devices[i].get_float_feature_value(dev_info["ExposureTime Key"]))
                except:
                    dev_info[dev_info["Gain Key"]].append(float(devices[i].get_integer_feature_value(dev_info["Gain Key"])))
                    dev_info[dev_info["ExposureTime Key"]].append(float(devices[i].get_integer_feature_value(dev_info["ExposureTime Key"])))

        for device in devices:
            del device

        Aravis.shutdown()

    test_info["acquisition-bb"] = get_bb_for_obtain_image(dev_info["Number of Devices"], dev_info["PixelFormat"])
    test_info["Red Gains"] = setting_config["r_gains"] if load_json else [1.0] * dev_info["Number of Devices"]
    test_info["Blue Gains"] = setting_config["g_gains"] if load_json else [1.0] * dev_info["Number of Devices"]
    test_info["Green Gains"] = setting_config["b_gains"] if load_json else [1.0] * dev_info["Number of Devices"]
    test_info["Gendc Mode"] = setting_config["gendc_mode"] if load_json and dev_info["GenDCStreamingMode"] else False
    test_info["Delete Bins"] = setting_config["delete_bin"] if load_json else True
    for key in dev_info:
        log_write("INFO", "{0:>20s} : {1}".format(key, dev_info[key]))

    for key in test_info:
        log_write("INFO", "{0:>20s} : {1}".format(key, test_info[key]))

    return dev_info, test_info


def required_bit_depth(pixelformat):
    if pfnc[pixelformat]["depth"] % 8 == 0:
        return pfnc[pixelformat]["depth"]
    else:
        required_byte_depth = pfnc[pixelformat]["depth"] // 8 + 1
        return required_byte_depth * 8


def get_bb_for_obtain_image(num_device, pixelformat):
    return "image_io_u3v_cameraN" + "_u" + str(required_bit_depth(pixelformat)) + "x" + str(

        pfnc[pixelformat]["dim"])


def get_num_bit_shift(pixelformat):
    return required_bit_depth(pixelformat) - pfnc[pixelformat]["depth"]


def get_bit_width(pixelformat):
    return pfnc[pixelformat]["depth"]


def normalize_to_uint8(pixelformat):
    return (pow(2, 8) - 1 ) / (pow(2, pfnc[pixelformat]["depth"]) - 1 )