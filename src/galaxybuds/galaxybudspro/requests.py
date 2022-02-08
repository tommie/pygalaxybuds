import dataclasses
import struct
import threading
from typing import Callable

from . import frames, messages

def debug_sku():
    return frames.Frame.make(0x22)

def debug_data():
    return frames.Frame.make(0x26)

def debug_serial_number():
    return frames.Frame.make(0x29)

def usage_report_response(code):
    return frames.Frame.make(0x40, messages.MsgSimple(struct.pack('<B', code)), response=True)

def noise_controls(v: int):
    return frames.Frame.make(0x78, messages.MsgSimple(struct.pack('<B', v)))

def set_equalizer_type(v: int):
    return frames.Frame.make(0x86, messages.MsgSimple(struct.pack('<B', v)))

def lock_touchpad(v: bool):
    return frames.Frame.make(0x90, messages.MsgSimple(struct.pack('<B', int(v))))

def set_touchpad_option(left: int, right: int):
    return frames.Frame.make(0x92, messages.MsgSimple(struct.pack('<BB', left, right)))

def set_noise_reduction(v: bool):
    return frames.Frame.make(0x98, messages.MsgSimple(struct.pack('<B', int(v))))

def start_find_my_earbuds():
    return frames.Frame.make(0xA0)

def stop_find_my_earbuds():
    return frames.Frame.make(0xA1)

def mute_earbud(left: bool, right: bool):
    return frames.Frame.make(0xA2, messages.MsgSimple(struct.pack('<BB', int(left), int(right))))

def update_time(time: int, tzoffset: int):
    return frames.Frame.make(0xA7, messages.MsgSimple(struct.pack('<LI', time, tzoffset)))

class MessageCache:
    """Listens for common messages and stores the last per type.

    This class is thread-safe.
    """

    def __init__(self, dispatcher: frames.FrameDispatcher):
        self.__dispatcher = dispatcher
        self.__data = {}
        self.__unlistens = []
        self.__merged_extended_status = None

        for id in [0x40, 0x41, 0x60, 0x61, 0x63, 0x77, 0x9C, 0xB9]:
            self.__unlistens.append(self.__listen(id))

        self.__cond = threading.Condition()

    def __listen(self, id: int) -> Callable[[], None]:
        self.__data[id] = None
        def setter(frame: frames.Frame):
            if not frame:
                return

            with self.__cond:
                # The earbuds start a connection by bursting extended
                # status, but then uses smaller updates.
                if id == 0x60 and self.__merged_extended_status:
                    fields = dataclasses.asdict(frame.message)
                    fields.pop('revision')
                    self.__merged_extended_status = dataclasses.replace(self.__merged_extended_status, **fields)
                elif id == 0x61:
                    self.__merged_extended_status = dataclasses.replace(frame.message)

                self.__data[id] = frame.message
                self.__cond.notify_all()

        self.__dispatcher.listen(id, setter)
        return lambda: self.__dispatcher.unlisten(id, setter)

    def close(self):
        """Deregisters from the frame dispatcher."""

        for func in self.__unlistens:
            func()
        self.__unlistens = []

    def wait_for(self, predicate: Callable[[], bool]):
        """Waits until a specific predicate returns true.

        Example to wait until a first value is received:

          values.wait_for(lambda: values.latest_usage_report)
        """

        with self.__cond:
            self.__cond.wait_for(predicate)

    @property
    def latest_usage_report(self):
        with self.__cond: return self.__data[0x40]

    @property
    def latest_metering_report(self):
        with self.__cond: return self.__data[0x41]

    @property
    def latest_status(self):
        with self.__cond: return self.__data[0x60]

    @property
    def latest_extended_status(self):
        with self.__cond: return self.__data[0x61]

    @property
    def latest_merged_extended_status(self) -> messages.MsgExtendedStatusUpdated:
        """The latest_extended_status property merged with other messages.

        The earbuds start a connection by bursting extended status,
        but then uses smaller updates. Prefer this over the raw
        latest_extended_status.
        """
        with self.__cond: return self.__merged_extended_status

    @property
    def version_info(self):
        with self.__cond: return self.__data[0x63]

    @property
    def latest_noise_controls_updated(self):
        with self.__cond: return self.__data[0x77]

    @property
    def latest_voice_wakeup_listening_status(self):
        with self.__cond: return self.__data[0x9C]

    @property
    def latest_fota_result(self):
        with self.__cond: return self.__data[0xB9]
