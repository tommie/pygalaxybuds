from collections.abc import Callable
import contextlib
import dataclasses
import logging
import struct
import threading
from typing import Type, TypeVar

import bluetooth

from . import messages

LOGGER = logging.getLogger('galaxybudspro.frames')

def crc16_ccitt(data: bytes):
    '''
    CRC-16 (CCITT) implemented with a precomputed lookup table

    From https://gist.github.com/oysstu/68072c44c02879a2abf94ef350d1c7c6?permalink_comment_id=3943460#gistcomment-3943460
    '''
    table = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7, 0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6, 0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485, 0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4, 0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
        0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823, 0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
        0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12, 0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
        0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41, 0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
        0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70, 0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
        0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F, 0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E, 0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D, 0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C, 0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB, 0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
        0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A, 0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
        0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9, 0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
        0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8, 0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
    ]

    crc = 0
    for byte in data:
        crc = (crc << 8) ^ table[(crc >> 8) ^ byte]
        crc &= 0xFFFF
    return crc

_FrameHeaderSubclass = TypeVar('_FrameHeaderSubclass', bound='FrameHeader')

@dataclasses.dataclass
class FrameHeader:
    """The header of a frame.

    See Frame for the encoding.
    """

    flags: int
    id: int

    @property
    def is_fragment(self): return self.flags & 0x2000 != 0

    @property
    def is_response(self): return self.flags & 0x1000 != 0

    @property
    def length(self): return self.flags & 0x3FF

    def encode(self) -> bytes:
        return struct.pack('<BHB', 0xFD, self.flags, self.id)

    @classmethod
    def parse(cls: Type[_FrameHeaderSubclass], data: bytes) -> tuple[_FrameHeaderSubclass, int]:
        if len(data) < 4:
            raise ValueError('short frame header length: {}'.format(len(data)))

        if data[0] != 0xFD:
            raise ValueError('invalid start-of-frame marker: 0x{:02X}'.format(data[0]))

        (flags, id) = struct.unpack('<HB', data[1:4])
        return cls(flags, id), 4

    @classmethod
    def make(cls: Type[_FrameHeaderSubclass], id: int, length: int, response=False, fragment=False) -> _FrameHeaderSubclass:
        flags = length
        if response: flags |= 0x1000
        if fragment: flags |= 0x2000
        return cls(flags, id)

_FrameSubclass = TypeVar('_FrameSubclass', bound='Frame')

@dataclasses.dataclass
class Frame:
    """The frame divides the RFCOMM stream into packets.

    Encoding:
      Most data is little-endian.

      1 byte   0xFD, start-of-frame marker.
      2 bytes  flags with bits
               0-9  length over the following bytes, excluding end-of-frame.
               11   whether this is a response to something.
               12   whether this is a fragment (i.e. not the last in a stream.)
      1 byte   message ID, i.e. the type of message.
      n bytes  message body, format depending on the ID.
      2 bytes  CRC16-CCITT in big-endian.
      1 byte   0xDD, end-of-frame marker.
    """

    header: FrameHeader
    body: bytes

    @property
    def message(self) -> messages.Msg:
        return messages.parse_message(self.header.id, self.body)

    def encode(self) -> bytes:
        return self.header.encode() + self.body + struct.pack('<HB', crc16_ccitt(bytes([self.header.id]) + self.body), 0xDD)

    @classmethod
    def parse(cls: Type[_FrameSubclass], header: FrameHeader, data: bytes) -> _FrameSubclass:
        if len(data) < 2 or 1 + len(data) != header.length:
            raise ValueError('short frame length: {}'.format(len(data)))

        crc = data[-1:] + data[-2:-1]
        if crc16_ccitt(bytes([header.id]) + data[:-2] + crc) != 0:
            raise ValueError('invalid CRC')

        return cls(header, data[:-2])

    @classmethod
    def make(cls: Type[_FrameSubclass], id: int, msg: messages.Msg=None, **kwargs) -> _FrameSubclass:
        body = msg.encode() if msg else b''
        return cls(FrameHeader.make(id, 1 + len(body) + 2, **kwargs), body)

class FrameReceiver:
    """Parses individual frames from a Bluetooth socket.

    This class is not thread-safe.
    """

    def __init__(self, sock: bluetooth.BluetoothSocket):
        self.__sock = sock
        self.__recvbuf = b''
        self.__closed = threading.Event()

    def close(self):
        """Closes the underlying socket, causing any current recv_frame calls to fail."""

        self.__closed.set()
        self.__sock.close()

    def recv_frame(self) -> Frame:
        """Parses and returns the next valid frame.

        Raises:
          EOFError if close() was called.
        """

        while True:
            # Find the next start-of-frame byte.
            self.__ensure_recvbuf(7) # SOF 2*Length ID [Body] 2*CRC EOF
            for i in range(len(self.__recvbuf)):
                if self.__recvbuf[i] == 0xFD:
                    break
            if i:
                LOGGER.warning('Lost non-framed data: %s', self.__recvbuf[:i])
                self.__recvbuf = self.__recvbuf[i:]
            if not self.__recvbuf or self.__recvbuf[0] != 0xFD:
                continue

            hdr, n = FrameHeader.parse(self.__recvbuf)
            self.__ensure_recvbuf(3 + hdr.length + 1)

            # Confirm the end of frame byte.
            if self.__recvbuf[3 + hdr.length] != 0xDD:
                LOGGER.warning('Lost data with bad framing: %s', self.__recvbuf[:3+hdr.length])
                self.__recvbuf = self.__recvbuf[1:]
                continue

            data = self.__recvbuf[n:3+hdr.length]
            self.__recvbuf = self.__recvbuf[3+hdr.length+1:]
            try:
                return Frame.parse(hdr, data)
            except ValueError as ex:
                LOGGER.warning('Lost invalid frame: %s', ex)

    def __ensure_recvbuf(self, n):
        """Ensures that __recvbuf contains at least n bytes."""

        while len(self.__recvbuf) < n:
            try:
                data = self.__sock.recv(0x800)
            except bluetooth.btcommon.BluetoothError as ex:
                if self.__closed.is_set() and ex.errno == 9:
                    raise EOFError()
                raise

            if data is None:
                if len(self.__recvbuf) < n:
                    raise IOError('short receive')
                return
            self.__recvbuf += data

class FrameDispatcher:
    """Receives frames in a background thread and invokes registered listeners.

    Listeners are run in a single thread, and thus shouldn't be
    blocking for too long.

    This class is thread-safe.
    """

    def __init__(self, receiver: FrameReceiver):
        self.__receiver = receiver
        self.__listeners = {}

        self.__lock = threading.Lock()
        self.__thread = threading.Thread(target=self.__run_recv, name=type(self).__name__)
        self.__thread.start()

    def close(self) -> None:
        """Closes the underlying receiver and waits for the background thread to exit."""

        self.__receiver.close()
        self.__thread.join()
        self.__thread = None
        self.__receiver = None

    def __run_recv(self) -> None:
        """Main function for the background thread."""

        try:
            while True:
                try:
                    try:
                        frame = self.__receiver.recv_frame()
                    except EOFError:
                        break

                    with self.__lock:
                        listeners = list(self.__listeners.get(frame.header.id, []))

                    for func in listeners:
                        try:
                            func(frame)
                        except Exception:
                            LOGGER.exception('FrameDispatcher thread listener failure (ignored)', exc_info=True)

                    LOGGER.debug('Dispatched frame header=%r body=%r listeners=%d', frame.header, frame.message or frame.body, len(listeners))
                except Exception:
                    LOGGER.exception('FrameDispatcher thread frame failure (ignored)', exc_info=True)
        except BaseException:
            LOGGER.exception('FrameDispatcher thread failed', exc_info=True)
            raise
        finally:
            with self.__lock:
                for funcs in self.__listeners.values():
                    for func in funcs:
                        func(None)

    def listen(self, id: int, func: Callable[[Frame], None]) -> None:
        """Registers a function to be invoked when the given message ID is seen.

        This is idempotent.
        """
        with self.__lock:
            if id not in self.__listeners:
                self.__listeners[id] = set()
            self.__listeners[id].add(func)

    def unlisten(self, id: int, func: Callable[[Frame], None]) -> None:
        """Deregisters a function previously used in listen().

        This is idempotent.
        """
        with self.__lock:
            if id not in self.__listeners:
                return
            self.__listeners[id].discard(func)

    @contextlib.contextmanager
    def oneshot(self, id: int, timeout: float=None, predicate: Callable[[messages.Msg], bool]=lambda _: True) -> Callable[[], messages.Msg]:
        """Listens for messages by ID and unlistens once seen.

        The returned function is used to wait for, and retrieve, the message.

        Example:

          with dispatcher.oneshot(0x42) as resultfunc:
            sock.send(...)
            result = resultfunc()
        """
        done = threading.Event()
        data = []
        def listener(frame: Frame):
            self.unlisten(id, listener)
            if frame:
                msg = frame.message
                if not predicate(msg):
                    return
                data.append(msg)
            else:
                data.append(None)
            done.set()

        def getter():
            if not done.wait(timeout=timeout):
                return None
            return data[0]

        self.listen(id, listener)
        try:
            yield getter
        finally:
            self.unlisten(id, listener)
