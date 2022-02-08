# Configuration Library for Galaxy Buds Pro

This library allows a user to change earbud settings like the
[Galaxy Buds Pro Manager app](https://play.google.com/store/apps/details?id=com.samsung.accessory.atticmgr&hl=en&gl=US). Implemented
as a Python library, meant as a prototype for researching the
protocol.

## Requirements

* Linux with Bluez.
* PyBluez is used to talk Bluetooth RFCOMM with the earbuds.

## Basic Example

Using the command line client:

```console
$ galaxybudsctl --address 01:23:45:67:89:ab --set-noise-cancelation off
KU: SM-R190NZKAEUD, SM-R190NZKAEUD
Upated noise cancelation mode.

$ galaxybudsctl --address 01:23:45:67:89:ab --listen-for status-changes
SKU: SM-R190NZKAEUD, SM-R190NZKAEUD
Listening for status changes...
STATUS placement_right 2
STATUS placement_right 3
^CStopped listening.
```

Using the library:

```python
import pprint

from galaxybuds.galaxybudspro import device

with device.Device.open() as buds:
    print('SKU:', buds.get_debug_sku())
    print('Serial:', buds.get_debug_serial_number())

    buds.status.wait_for(lambda: buds.status.version_info)
    print('Version: ', end='')
    pprint.pprint(dataclasses.asdict(buds.status.version_info))

    buds.status.wait_for(lambda: buds.status.latest_merged_extended_status)
    print('Status: ', end='')
    pprint.pprint(dataclasses.asdict(buds.status.latest_merged_extended_status))
```

(In Python >=3.10, `pprint` handles dataclasses, which means
the `asdict()` can be removed.)

## Features

See `device.py` for implemented high-level methods, file changing
noise cancellation settings, changing touchpad functionality and
controlling Find My Earbuds.

## Known Issues

* If the library cannot find any device, pass the earbuds' Bluetooth
  address, like `open('00:11:22:33:44:55')`. This seems to be an issue
  with PyBluez on at least Ubuntu 21.10.
* Sometimes, the background receive thread bombs out when closing the
  socket, instead of gracefully shutting down.
* As with all request-response formats, there's a chance the response
  is missed, or not generated, and a request hangs forever. The
  `frames.FrameDispatcher.oneshot` supports timeouts, but it's not
  been plumbed through to `Device`.
* To use the app-launching functionality of the touchpad, you need the
  app installed, though this library could be used to emulate that
  too. See `device.Device.listen_for_touch_and_hold_app`.
* The `device.Device.status` field contains fields with raw
  `messages.Msg` types. This isn't pretty and should be cleaned up.

## Fun Facts

* The earbuds can coredump, and a debugger can fetch the core dumps.
* I originally thought "wouldn't it be cool to build a web page with
  the
  [Web Bluetooth API](https://webbluetoothcg.github.io/web-bluetooth/)
  to change earbud settings?" Turns out
  [RFCOMM is out of scope](https://github.com/WebBluetoothCG/web-bluetooth/blob/main/charter.md#out-of-scope). Too
  bad. Resorting to Python for prototyping.

## Protocol Outline

The earbuds use an (insecure) RFCOMM socket, acting like a serial
stream. The stream is divided into frames, with a type byte describing
the contents. There is support for fragments, but it's sparingly used
(perhaps only for OTA firmware updates). The frames contain

* Start-of-frame marker
* Length and flags
* ID/type
* Payload
* CRC16
* End-of-frame marker

For more information, see `Frame` and `FrameReceiver` in
`frames.py`. The payload is parsed by `parse_message` in
`messages.py`.

## Origin

The information used to make this possible is based on the Galaxy Buds
Pro Manager for Android.

The library was created because the author doesn't want to run the
risk of the earbuds receiving a bad firmware upgrade while configuring
them. There are some reports in Play Store about bugs in the app.

## License

The Git repository is released under the MIT License.
