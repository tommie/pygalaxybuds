import dataclasses
import struct

from . import redirect_messages

class Msg:
    pass

@dataclasses.dataclass
class MsgStringPair(Msg):
    data: [str, str]

    @classmethod
    def parse(cls, data: bytes):
        if len(data) % 2 == 1:
            raise ValueError('expected an even number of bytes for StringPair, got {}'.format(len(data)))

        n = len(data) // 2
        return cls((data[:n].decode('ascii'), data[n:].decode('ascii')))

@dataclasses.dataclass
class MsgStatusUpdated(Msg):
    revision: int # always zero?
    batteryLeft: int
    batteryRight: int
    coupled: bool
    primaryEarbud: int
    placementLeft: int
    placementRight: int # lower nibble
    batteryCase_: int

    @property
    def batteryCase(self):
        if self.batteryCase_ == 101:
            return -1
        return self.batteryCase_

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 7:
            raise ValueError('expected at least 7 bytes ExtendedStatusUpdated, got {}'.format(len(data)))

        i = 0
        args = struct.unpack('<5B', data[i:i+5])
        i += 5
        args += (
            data[i] >> 4,
            data[i] & 0x0F,
        )
        i += 1
        args += (data[i],)
        i += 1

        if i != len(data):
            raise ValueError('unable to parse the MsgStatusUpdated, expected length {}, got {}'.format(i, len(data)))

        return cls(*args)

@dataclasses.dataclass
class MsgExtendedStatusUpdated(Msg):
    revision: int
    earType: int
    batteryLeft: int
    batteryRight: int
    coupled: bool
    primaryEarbud: int
    placementLeft: int  # 1: wearing, 2: table, 3: case
    placementRight: int # lower nibble
    batteryCase_: int
    adjustSoundSync: bool
    equalizerType: int
    touchpadConfig: bool
    touchpadOptionLeft: int
    touchpadOptionRight: int # lower nibble
    noiseControls: int
    voiceWakeUp: bool
    deviceColor_: int # 2 shorts
    voiceWakeUpLanguage: int
    seamlessConnection: bool # negated
    fmmRevision: int
    noiseControlsOff: bool # bit 0
    noiseControlsAmbient: bool # bit 1
    noiseControlsAnc: bool # bit 2
    leftNoiseControlsOff: bool # bit 4, rev>=8
    leftNoiseControlsAmbient: bool # bit 5, rev>=8
    leftNoiseControlsAnc: bool # bit 6, rev>=8
    extraHighAmbient1: bool # rev<3
    speakSeamlessly: bool # rev>=3
    ambientSoundLevel: int
    noiseReductionLevel: int
    autoSwitchAudioOutput: bool
    detectConversations: bool
    detectConversationsDuration_: int
    spatialAudio: bool # rev>=2
    hearingEnhancements: int # rev>=5
    extraHighAmbient2: bool # rev>=6
    outsideDoubleTap: bool # rev>=7
    noiseControlsWithOneEarbud: bool # rev>=8
    customizeAmbientSoundOn: bool # rev>=8
    customizeAmbientVolumeLeft: int # rev>=8
    customizeAmbientVolumeRight: int # lower nibble, rev>=8
    ambientSoundTone: int  # rev>=8
    sideTone: bool # rev>=9
    callPathControl: bool # negated, if in_ear_detection feature (rev>=10 ?)

    @property
    def batteryCase(self):
        if self.batteryCase_ == 101:
            return -1
        return self.batteryCase_

    @property
    def deviceColor(self):
        if (self.coupled and self.deviceColor_[1]) or (not self.coupled and not self.primaryEarbud):
            return self.deviceColor_[1]
        return self.deviceColor_[0]

    @property
    def extraHighAmbient(self):
        if self.revision < 3:
            return self.extraHighAmbient1
        if self.revision >= 6:
            return self.extraHighAmbient2
        return 0

    @property
    def detectConversationsDuration(self):
        if self.detectConversationsDuration_ < 2:
            return 1
        return detectConversationsDuration_

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 25:
            raise ValueError('expected at least 25 bytes ExtendedStatusUpdated, got {}'.format(len(data)))

        i = 0
        args = struct.unpack('<6B', data[i:i+6])
        i += 6
        args += (
            data[i] >> 4,
            data[i] & 0x0F,
        )
        i += 1
        args += struct.unpack('<4B', data[i:i+4])
        i += 4
        args += (
            data[i] >> 4,
            data[i] & 0x0F,
        )
        i += 1
        args += struct.unpack('<2B', data[i:i+2])
        i += 2
        v = struct.unpack('<2H', data[i:i+4])
        args += (v,)
        i += 4
        args += struct.unpack('<3B', data[i:i+3])
        i += 3
        rev = args[0]

        v = data[i]
        i += 1
        args += (
            v & 1 != 0,
            v & 2 != 0,
            v & 4 != 0,
        )
        if rev >= 8:
            args += (
                v & 16 != 0,
                v & 32 != 0,
                v & 64 != 0,
            )
        else:
            args += (None,) * 3

        if rev < 3:
            args += (data[i], None)
            i += 1
        else:
            args += (None, data[i])
            i += 1

        args += struct.unpack('<5B', data[i:i+5])
        i += 5

        if rev >= 2:
            args += (data[i] != 0,)
            i += 1
        else:
            args += (None,)

        if rev >= 5:
            args += (data[i],)
            i += 1
        else:
            args += (None,)

        if rev >= 6: # extraHighAmbient moved from earlier.
            args += (data[i] != 0,)
            i += 1
        else:
            args += (None,)

        if rev >= 7:
            args += (data[i] != 0,)
            i += 1
        else:
            args += (None,)

        if rev >= 8:
            v = struct.unpack('<4B', data[i:i+4])
            i += 4
            args += (
                v[0] != 0,
                v[1] != 0,
                v[2] >> 4,
                v[2] & 0x0F,
                v[3],
            )
        else:
            args += (None,) * 5

        if rev >= 9:
            args += (data[i],)
            i += 1
        else:
            args += (None,)

        if rev >= 10:
            args += (data[i] == 0,)
            i += 1
        else:
            args += (None,)

        if i != len(data):
            raise ValueError('unable to parse the MsgExtendedStatusUpdated, expected length {}, got {}'.format(i, len(data)))

        return cls(*args)

@dataclasses.dataclass
class MsgVersionInfo(Msg):
    right_hw_version: int
    left_hw_version: int
    left_sw_version_flags: int
    left_sw_version_date: int
    left_sw_version_ver: int
    right_sw_version_flags: int
    right_sw_version_date: int
    right_sw_version_ver: int
    left_touch_fw_version: int
    right_touch_fw_version: int

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 10:
            raise ValueError('expected at least 10 bytes VersionInfo, got {}'.format(len(data)))

        # Galaxy Buds Pro have model number SM-R190, but this is implied.
        return cls(
            right_hw_version=data[0],
            left_hw_version=data[1],
            left_sw_version_flags=data[2],
            left_sw_version_date=data[3],
            left_sw_version_ver=data[4],
            right_sw_version_flags=data[5],
            right_sw_version_date=data[6],
            right_sw_version_ver=data[7],
            left_touch_fw_version=data[8],
            right_touch_fw_version=data[9],
        )

@dataclasses.dataclass
class MsgNoiseControlsUpdate(Msg):
    noise_controls_update: int
    wearing_state: int

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 2:
            raise ValueError('expected at least 2 bytes NoiseControlsUpdate, got {}'.format(len(data)))

        return cls(
            noise_controls_update=data[0],
            wearing_state=data[1],
        )

@dataclasses.dataclass
class MsgVoiceWakeupListeningStatus(Msg):
    status: bool

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 1:
            raise ValueError('expected at least 1 byte VoiceWakeupListeningStatus, got {}'.format(len(data)))

        return cls(
            status=data[0],
        )

@dataclasses.dataclass
class MsgFotaResult(Msg):
    result: int
    error_code: int

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 2:
            raise ValueError('expected at least 2 bytes FotaResult, got {}'.format(len(data)))

        return cls(
            result=data[0],
            error_code=data[1],
        )

@dataclasses.dataclass
class MsgUsageReport(Msg):
    entries: dict[int, int]

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 1:
            raise ValueError('expected at least 1 byte UsageReport, got {}'.format(len(data)))

        n = data[0]
        if len(data) - 1 != 9 * n:
            raise ValueError('expected {} bytes of data for {} entries, got {}'.format(9 * n, n, len(data) - 1))

        def str_key(data):
            v = data
            ei = v.find(b'\x00')
            if ei >= 0: v = data[:ei]
            return v.decode('ascii')

        return cls(
            entries={str_key(data[i:i+5]): struct.unpack('<I', data[i+5:i+9])[0] for i in range(1, 1 + 9*n, 9)},
        )

@dataclasses.dataclass
class MsgMeteringReport(Msg):
    format: int
    # Left, Right
    connected_side: tuple[bool, bool]
    total_battery_capacity: int
    battery: tuple[int, int]
    a2dp_using_time: tuple[int, int]
    esco_open_time: tuple[int, int]
    anc_on_time: tuple[int, int]
    ambient_on_time: tuple[int, int]

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 2:
            raise ValueError('expected at least 2 bytes MeteringReport, got {}'.format(len(data)))

        fmt = data[0]
        connected_side = (data[1] >> 4, data[1] & 0x0F)
        args = (fmt, connected_side)
        i = 2

        if fmt >= 2:
            args += struct.unpack('<H', data[i:i+2])
            i += 2
        else:
            args += (None,)

        sides = []
        for j in range(2):
            if connected_side[j]:
                sides.append(struct.unpack('<B4I', data[i:i+17]))
            else:
                sides.append((None,) * 5)
        args += tuple(zip(*sides))

        return cls(*args)

@dataclasses.dataclass
class MsgUniversalAcknowledgement(Msg):
    redirect_id: int
    redirect_body: bytes

    @property
    def redirect_message(self) -> redirect_messages.RedirectMsg:
        return redirect_messages.parse_message(self.redirect_id, self.redirect_body)

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 1:
            raise ValueError('expected at least 1 byte UniversalAcknowledgement, got {}'.format(len(data)))

        return cls(
            redirect_id=data[0],
            redirect_body=data[1:],
        )

@dataclasses.dataclass
class MsgTouchPadOther(Msg):
    other_option: int

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 1:
            raise ValueError('expected at least 1 byte TouchPadOther, got {}'.format(len(data)))

        return cls(
            other_option=data[0],
        )

@dataclasses.dataclass
class MsgSimple(Msg):
    data: bytes

    def encode(self):
        return self.data

    @classmethod
    def parse(cls, data: bytes):
        return cls(data)

def parse_message(id: int, data: bytes):
    if id == 0xAC:  # SetFmmConfig, SET_FMM_CONFIG
        pass
    elif id == 0xAD:  # GetFmmConfig, GET_FMM_CONFIG
        pass
    elif id == 0xC2:  # (Spatial sensor data)
        # Handled by ShtCore and SppRecvHelper.
        # First byte is type: 0x20: GRV, 0x21: Wear on update, 0x22: Wear off update, 0x23: Gyro bias, 0x24: Stuck info.
        return MsgSimple.parse(data)
    elif id == 0xC3:  # (Spatial sensor control)
        # Single byte: 2: addSuccess, 3: removeSuccess
        return MsgSimple.parse(data)
    elif id == 0x4A:  # AgingTestReport
        pass
    elif id == 0x4B:
        # Ignored in CoreServiceModel.
        return MsgSimple.parse(data)
    elif id == 0x60:  # StatusUpdated, MSG_ID_STATUS_UPDATED
        return MsgStatusUpdated.parse(data)
    elif id == 0x61:  # ExtendedStatusUpdated, MSG_ID_EXTENDED_STATUS_UPDATED
        return MsgExtendedStatusUpdated.parse(data)
    elif id == 0x22:  # DebugSKU
        # Handled by CoreServiceModel.
        return MsgStringPair.parse(data)
    elif id == 0x26:  # DebugData, DEBUG_ALL_DATA
        pass
    elif id == 0x29:  # DebugSerial, DEBUG_SERIAL_NUMBER
        return MsgStringPair.parse(data)
    elif id == 0x50:  # Reset
        pass
    elif id == 0x63:  # VersionInfo, MSG_ID_VERSION_INFO
        return MsgVersionInfo.parse(data)
    elif id == 0x77:  # NoiseControlsUpdate, MSG_ID_NOISE_CONTROLS_UPDATE
        # Handled by CoreServiceModel.
        return MsgNoiseControlsUpdate.parse(data)
    elif id == 0x9A:  # VoiceWakeUpEvent, VOICE_WAKE_UP_EVENT
        # Handled by CoreServiceModel.
        pass
    elif id == 0x9B:  # NoiseReductionModeUpdated, NOISE_REDUCTION_MODE_UPDATE
        # Handled by CoreServiceModel.
        pass
    elif id == 0x9C:  # VoiceWakeUpListeningStatus, VOICE_WAKE_UP_LISTENING_STATUS
        # Handled by CoreServiceModel.
        return MsgVoiceWakeupListeningStatus.parse(data)
    elif id == 0x31:  # LogCoredumpDataSize, LOG_COREDUMP_DATA_SIZE
        pass
        # Handled by DeviceLogManager.
    elif id == 0x32:  # LogCoredumpData, LOG_COREDUMP_DATA
        pass
    elif id == 0x33:  # LogCoredumpComplete, LOG_COREDUMP_COMPLETE
        pass
    elif id == 0x34:  # LogTraceStart, LOG_TRACE_START
        pass
    elif id == 0x35:  # LogTraceData, LOG_TRACE_DATA
        pass
    elif id == 0x36:  # LogTraceComplete, LOG_TRACE_COMPLETE
        pass
    elif id == 0x37:  # LogRoleSwitch, LOG_TRACE_ROLE_SWITCH
        pass
    elif id == 0x38:  # LogCoredumpTransmissionDone, LOG_COREDUMP_DATA_DONE
        pass
    elif id == 0x39:  # LogTraceTransmissionDone, LOG_TRACE_DATA_DONE
        pass
    elif id == 0x3A:  # LogSessionOpen, LOG_SESSION_OPEN
        pass
    elif id == 0x3B:  # LogSessionClose, LOG_SESSION_CLOSE
        pass
    elif id == 0xB9:  # FotaResult, MSG_ID_FOTA_RESULT
        # Handled by FotaTransferManager.
        return MsgFotaResult.parse(data)
    elif id == 0xBA:  # FotaEmergency, FOTA_EMERGENCY
        pass
        # Sends MsgFotaEmergency 0xBA response.
    elif id == 0xBB:  # FotaSession, MSG_ID_FOTA_OPEN
        pass
    elif id == 0xBC:  # FotaControl, MSG_ID_FOTA_CONTROL
        # Sends MsgFotaControl.
        pass
    elif id == 0xBD:  # FotaDownloadData, MSG_ID_FOTA_DOWNLOAD_DATA
        # Sends MsgFotaDownloadData.
        pass
    elif id == 0xBE:  # FotaUpdated, MSG_ID_FOTA_UPDATE
        pass
    elif id == 0x40:  # UsageReport, USAGE_REPORT
        # Handled by EarBudsUsageReporter.
        # Sends MsgUsageReport(responseCode) back.
        # We raise an exception instead of setting responseCode for now.
        return MsgUsageReport.parse(data)
    elif id == 0x41:  # MeteringReport, METERING
        return MsgMeteringReport.parse(data)
    elif id == 0x42:  # UniversalAcknowledgement, UNIVERSAL_MSG_ID_ACKNOWLEDGEMENT
        return MsgUniversalAcknowledgement.parse(data)
    elif id == 0x88:  # ManagerInfo
        pass
    elif id == 0x8A:  # SetInBandRingtone, SET_IN_BAND_RINGTONE
        pass
    elif id == 0x91:  # TouchUpdated, TOUCH_UPDATED
        # touchpadLocked = status == 1
        pass
    elif id == 0x93:  # TouchPadOther, TOUCHPAD_OTHER_OPTION
        # touchpadOtherOptionValue == 4 -> Spotify
        # touchpadOtherOptionValue == 5 -> left something
        # touchpadOtherOptionValue >= 6 -> right something
        # MsgSetTouchpadOption TODO
        return MsgTouchPadOther.parse(data)
    elif id == 0x9E:  # CheckTheFitOfEarbudsResult, CHECK_THE_FIT_OF_EARBUDS_RESULT
        # Handled by CoreServiceModel.
        pass
    elif id == 0xA1: # FIND_MY_EARBUDS_STOP
        return MsgSimple.parse(data)
    elif id == 0xA5: # VOICE_NOTI_STOP
        return MsgSimple.parse(data)
    elif id == 0x6D: # AMBIENT_DURING_CALL_NOTI
        # Handled by AmbientSoundDuringsCallNotiReceiver
        return MsgSimple.parse(data)
    elif id == 0xA3:  # MuteEarbudStatusUpdated, MUTE_EARBUD_STATUS_UPDATED
        pass
    elif id == 0xB4:  # FotaDeviceInfoSwVersion, FOTA_DEVICE_INFO_SW_VERSION
        pass

    # These don't seem to be parsed: 0x2D, 0x2E, 0x2F, 0x74, 0x75, 0xF1, 0xF2

    return None
