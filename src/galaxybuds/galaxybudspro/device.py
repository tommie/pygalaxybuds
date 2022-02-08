import contextlib
import enum
import threading
from typing import Callable, Type, TypeVar, Union

import bluetooth

from . import frames, redirect_messages, requests

class EqualizerType(enum.Enum):
    NORMAL = 0
    BASS_BOOST = 1
    SOFT = 2
    DYNAMIC = 3
    CLEAR = 4
    TREBLE_BOOST = 5

class NoiseControls(enum.Enum):
    OFF = 0
    ANC = 1
    AMBIENT_SOUNDS = 2

class TouchpadOption(enum.Enum):
    ANC = 2 # Toggles between ANC and AMBIENT_SOUNDS.
    VOLUME = 3 # Right is up, left is down.
    SPOTIFY = 4 # Hard-coded in the app.
    APP5 = 5 # Configurable in the app.
    APP6 = 6 # Configurable in the app.

_DeviceSubclass = TypeVar('_DeviceSubclass', bound='Device')

class Device:
    """A Galaxy Buds Pro device.

    This class is thread-safe.
    """

    def __init__(self, sock: bluetooth.BluetoothSocket):
        self.__sock = sock
        self.__dispatcher = frames.FrameDispatcher(frames.FrameReceiver(sock))
        self.__send_lock = threading.Lock()
        self.status = requests.MessageCache(self.__dispatcher)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.status.close()
        self.__sock.close()
        self.__sock = None
        self.__dispatcher.close()
        self.__dispatcher = None

    @classmethod
    def open(cls: Type[_DeviceSubclass], address: str=None) -> _DeviceSubclass:
        """Opens a Bluetooth socket and returns a device."""

        devs = bluetooth.find_service(name='GEARMANAGER', uuid='00001101-0000-1000-8000-00805F9B34FB', address=address)

        if len(devs) != 1:
            raise IOError('expected exactly one device, got {}'.format(len(devs)))

        dev = devs[0]

        if dev['protocol'] != 'RFCOMM':
            raise IOError('expected RFCOMM protocol, got {}'.format(dev['protocol']))

        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        sock.connect((dev['host'], dev['port']))
        return cls(sock)

    def get_debug_sku(self):
        """Returns the SKU (product code) of the left and right earbud."""

        with self.__dispatcher.oneshot(0x22) as get:
            with self.__send_lock:
                self.__sock.send(requests.debug_sku().encode())
            result = get()
        return result.data if result else None

    def get_debug_serial_number(self):
        """Returns the serial number of the left and right earbud."""

        with self.__dispatcher.oneshot(0x29) as get:
            with self.__send_lock:
                self.__sock.send(requests.debug_serial_number().encode())
            result = get()
        return result.data if result else None

    def start_find_my_earbuds(self):
        """Makes the earbuds start chirping.

        This stops automatically when the Bluetooth socket is closed.
        """
        with self.__oneshot_ack(0xA0) as get:
            with self.__send_lock:
                self.__sock.send(requests.start_find_my_earbuds().encode())
            get()

    def stop_find_my_earbuds(self):
        """Stops the chirping started with start_find_my_earbuds()."""

        with self.__oneshot_ack(0xA1) as get:
            with self.__send_lock:
                self.__sock.send(requests.stop_find_my_earbuds().encode())
            get()

    def mute_earbud(self, left: bool, right: bool) -> None:
        """Mutes the find-my-earbuds chirp."""

        with self.__oneshot_ack(0xA2) as get:
            with self.__send_lock:
                self.__sock.send(requests.mute_earbud(left, right).encode())
            get()

    def set_equalizer_type(self, v: EqualizerType) -> None:
        """Sets the sound equalizing."""

        if not (0 <= v.value <= 5):
            raise ValueError('expected a value in [0, 5]: {}'.format(v))

        with self.__oneshot_ack(0x86) as get:
            with self.__send_lock:
                self.__sock.send(requests.set_equalizer_type(v.value).encode())
            get()

    def set_noise_controls(self, v: NoiseControls) -> None:
        """Sets the noise reduction level."""

        if not (0 <= v.value <= 2):
            raise ValueError('expected a value in [0, 2]: {}'.format(v))

        with self.__oneshot_ack(0x78) as get:
            with self.__send_lock:
                self.__sock.send(requests.noise_controls(v.value).encode())
            get()

    def set_noise_reduction(self, enabled: bool) -> None:
        """Sets the noise reduction state.

        This is likely an older version of set_noise_controls().
        """
        with self.__dispatcher.oneshot(0x77, predicate=lambda msg: msg.noise_controls_update == int(enabled)) as get:
            with self.__send_lock:
                self.__sock.send(requests.set_noise_reduction(enabled).encode())
            get()

    def set_touchpad_enabled(self, enabled: bool) -> None:
        """Sets whether the touchpad should be enabled or not."""

        with self.__oneshot_ack(0x90) as get:
            with self.__send_lock:
                self.__sock.send(requests.lock_touchpad(not enabled).encode())
            get()

    def set_touchpad_option(self, left: TouchpadOption, right: TouchpadOption) -> None:
        """Sets the actions for touching the earbuds."""

        if not (2 <= left.value <= 6):
            raise ValueError('expected a left value in [2, 6]: {}'.format(left))
        if not (2 <= right.value <= 6):
            raise ValueError('expected a right value in [2, 6]: {}'.format(right))

        with self.__oneshot_ack(0x92) as get:
            with self.__send_lock:
                self.__sock.send(requests.set_touchpad_option(left.value, right.value).encode())
            get()

    def listen_for_touch_and_hold_app(self, func: Callable[[Union[TouchpadOption, None]], None]) -> Callable[[], None]:
        """Waits for the user to touch-and-hold to open an app.

        The integer passed to the callback is what was set with
        `set_touchpad_option`. 4 is normally hard-coded as
        Spotify. 5-6 are configurable in the app.

        When the device connection is lost, the callback is invoked
        with None.

        Returns a function to cancel the listener.

        """
        def listener(frame: frames.Frame):
            if not frame:
                func(None)
            else:
                func(TouchpadOption(frame.message.other_option))

        self.__dispatcher.listen(0x93, listener)
        return lambda: self.__dispatcher.unlisten(0x93, listener)

    @contextlib.contextmanager
    def __oneshot_ack(self, redirect_id: int, **kwargs) -> Callable[[], redirect_messages.RedirectMsg]:
        """Like dispatcher.oneshot(), but waits for a UniversalAcknowledgement with the given redirect ID."""

        with self.__dispatcher.oneshot(0x42, predicate=lambda msg: msg.redirect_id == redirect_id, **kwargs) as getter:
            def redirect_getter():
                result = getter()
                return result.redirect_message if result else None

            yield redirect_getter
