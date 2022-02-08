import dataclasses

class RedirectMsg:
    pass

@dataclasses.dataclass
class RedirectMsgNoiseControls(RedirectMsg):
    noise_controls: int

    @classmethod
    def parse(cls, data: bytes):
        if len(data) < 1:
            raise ValueError('expected at least 1 byte NoiseControls, got {}'.format(len(data)))

        return cls(data[0])

def parse_message(id: int, data: bytes) -> RedirectMsg:
    if id == 0x78:
        return RedirectMsgNoiseControls.parse(data)

    return None
