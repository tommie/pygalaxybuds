"""An example control program for Galaxy Buds Pro.

Examples:

  PYTHONPATH=src python3 -m galaxybuds.command.galaxybudsctl --print all
  PYTHONPATH=src python3 -m galaxybuds.command.galaxybudsctl --set-noise-cancelation off
  PYTHONPATH=src python3 -m galaxybuds.command.galaxybudsctl --print serial --set-touchpad-options spotify,app5
"""

import argparse
import dataclasses
import logging
import sys
import time

from galaxybuds.galaxybudspro import device

ALL_PRINTABLE = ['serial', 'sku', 'status', 'version']

def print_information(buds: device.Device, toprint: set[str]):
    if 'serial' in toprint:
        print('Serial:', ', '.join(buds.get_debug_serial_number()))

    if 'sku' in toprint:
        print('SKU:', ', '.join(buds.get_debug_sku()))

    if 'status' in toprint:
        print('Status:')
        buds.status.wait_for(lambda: buds.status.latest_extended_status)
        for k, v in dataclasses.asdict(buds.status.latest_extended_status).items():
            print('  {}: {}'.format(k, v))

    if 'version' in toprint:
        print('Version:')
        buds.status.wait_for(lambda: buds.status.version_info)
        for k, v in dataclasses.asdict(buds.status.version_info).items():
            print('  {}: {}'.format(k, v))

def find_my_earbuds(buds: device.Device, which: set[str]):
    buds.start_find_my_earbuds()
    try:
        buds.mute_earbud('left' not in which, 'right' not in which)
        print('Chirping {} for 30 seconds...'.format(' and '.join(sorted(which))))
        time.sleep(30)
    except KeyboardInterrupt:
        print('Stopped chirp.')
    finally:
        buds.stop_find_my_earbuds()

def set_equalizer(buds: device.Device, typ: device.EqualizerType):
    buds.set_equalizer_type(typ)
    print('Upated equalizer type.')

def set_noise_cancelation(buds: device.Device, typ: device.NoiseControls):
    buds.set_noise_controls(typ)
    print('Upated noise cancelation mode.')

def set_touchpad_enabled(buds: device.Device, enabled: bool):
    buds.set_touchpad_enabled(enabled)
    print('Updated touchpad locking.')

def set_touchpad_options(buds: device.Device, options: list[device.TouchpadOption]):
    buds.set_touchpad_option(options[0], options[1])
    print('Updated touchpad options.')

def listen_for_touch_and_hold_app(buds: device.Device):
    print('Listening for touch and hold events...', file=sys.stderr)
    unlisten = buds.listen_for_touch_and_hold_app(lambda option: print('TOUCH', option.name.lower()))
    try:
        # Emulates signal.pause.
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print('Stopped listening.', file=sys.stderr)
    finally:
        unlisten()

def main():
    parser = argparse.ArgumentParser(description='Control Galaxy Buds Pro earbuds over Bluetooth.')
    parser.add_argument('--address', metavar='XX:XX:XX:XX:XX:XX', type=str, help='the Bluetooth address to connect to')
    parser.add_argument('--log-level', default='warning', type=str, help='the logging level',
                        choices=['debug', 'info', 'warning', 'error'])
    parser.add_argument('--print', default=['sku'], action='append', type=str, help='comma-separated list of information to print',
                        choices=['all'] + ALL_PRINTABLE)
    parser.add_argument('--find-my-earbuds', nargs='?', const='both', help='enable a loud chirp in the buds for 30 seconds',
                        choices=['both', 'left', 'right'])
    parser.add_argument('--set-equalizer', type=str, help='sets the sound equalizer mode',
                        choices=sorted(v.name.lower().replace('_', '-') for v in device.EqualizerType))
    parser.add_argument('--set-noise-cancelation', type=str, help='sets the noise cancelation mode',
                        choices=sorted(v.name.lower().replace('_', '-') for v in device.NoiseControls))
    parser.add_argument('--set-touchpad', type=str, help='sets whether the touchpad is locked',
                        choices=['locked', 'unlocked'])
    parser.add_argument('--set-touchpad-options', type=str, help='sets the touch-and-hold functionality of each earbud',
                        metavar='LEFT[,RIGHT] {{{}}}'.format(','.join(sorted(v.name.lower() for v in device.TouchpadOption))))
    parser.add_argument('--listen-for-touch-and-hold-app', action='store_true', help='listens for touch-and-hold events and prints them to stdout')
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stderr, level=args.log_level.upper())

    with device.Device.open(args.address) as buds:
        toprint = {v.lower() for vs in args.print for v in vs.split(',') if v}
        if 'all' in toprint:
            toprint |= set(ALL_PRINTABLE)
        if toprint:
            print_information(buds, toprint)

        if args.find_my_earbuds == 'both':
            args.find_my_earbuds = {'left', 'right'}
        elif args.find_my_earbuds:
            args.find_my_earbuds = {args.find_my_earbuds}
        if args.find_my_earbuds:
            find_my_earbuds(buds, args.find_my_earbuds)

        if args.set_equalizer:
            set_equalizer(buds, device.EqualizerType[args.set_equalizer.replace('-', '_').upper()])

        if args.set_noise_cancelation:
            set_noise_cancelation(buds, device.NoiseControls[args.set_noise_cancelation.replace('-', '_').upper()])

        if args.set_touchpad:
            set_touchpad_enabled(buds, args.set_touchpad == 'unlocked')

        if args.set_touchpad_options:
            args.set_touchpad_options = [device.TouchpadOption[v.upper()] for v in args.set_touchpad_options.split(',')]
            if len(args.set_touchpad_options) == 1:
                args.set_touchpad_options *= 2
            if len(args.set_touchpad_options) != 2:
                print('Expected exactly two touchpad options, but got {}'.format(','.join(args.set_touchpad_options)), file=sys.stderr)
            set_touchpad_options(buds, args.set_touchpad_options)

        if args.listen_for_touch_and_hold_app:
            listen_for_touch_and_hold_app(buds)

if __name__ == '__main__':
    main()
