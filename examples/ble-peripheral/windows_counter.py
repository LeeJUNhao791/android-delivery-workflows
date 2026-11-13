"""Advertise a disposable BLE counter on a Windows adapter."""

import argparse
import asyncio
from contextlib import asynccontextmanager
import struct
import time
from uuid import UUID

from winrt.windows.devices.bluetooth import BluetoothAdapter, BluetoothError
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattCharacteristicProperties,
    GattLocalCharacteristicParameters,
    GattProtectionLevel,
    GattServiceProvider,
    GattServiceProviderAdvertisingParameters,
    GattServiceProviderAdvertisementStatus,
)
from winrt.windows.devices.radios import RadioAccessStatus, RadioState
from winrt.windows.storage.streams import DataWriter

SERVICE = UUID("af727351-9e73-4412-a11b-44ef95814b20")
COUNTER = UUID("af727352-9e73-4412-a11b-44ef95814b20")


def log(message):
    print(message, flush=True)


async def set_radio(radio, state):
    if radio.state != state:
        status = await radio.set_state_async(state)
        if status != RadioAccessStatus.ALLOWED:
            raise RuntimeError(f"Cannot set Bluetooth radio to {state.name}: {status.name}")
        deadline = time.monotonic() + 8
        while radio.state != state:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Bluetooth radio did not switch to {state.name}")
            await asyncio.sleep(0.25)


def payload(counter):
    writer = DataWriter()
    writer.write_bytes(struct.pack("<I", counter))
    return writer.detach_buffer()


@asynccontextmanager
async def advertise(start):
    service = await GattServiceProvider.create_async(SERVICE)
    if service.error != BluetoothError.SUCCESS:
        raise RuntimeError(f"Cannot create GATT service: {service.error.name}")
    provider = service.service_provider
    parameters = GattLocalCharacteristicParameters()
    parameters.characteristic_properties = (
        GattCharacteristicProperties.READ | GattCharacteristicProperties.NOTIFY
    )
    parameters.read_protection_level = GattProtectionLevel.PLAIN
    result = await provider.service.create_characteristic_async(COUNTER, parameters)
    if result.error != BluetoothError.SUCCESS:
        raise RuntimeError(f"Cannot create counter characteristic: {result.error.name}")
    characteristic = result.characteristic
    loop = asyncio.get_running_loop()

    async def respond(args, deferral):
        try:
            request = await args.get_request_async()
            if request is not None:
                request.respond_with_value(payload(int(time.monotonic() - start)))
        except OSError as error:
            log(f"READ_ERROR {error}")
        finally:
            deferral.complete()

    def read_requested(sender, args):
        deferral = args.get_deferral()
        asyncio.run_coroutine_threadsafe(respond(args, deferral), loop)

    token = characteristic.add_read_requested(read_requested)
    advertising = GattServiceProviderAdvertisingParameters()
    advertising.is_connectable = True
    advertising.is_discoverable = True
    try:
        provider.start_advertising_with_parameters(advertising)
        for _ in range(40):
            if provider.advertisement_status == GattServiceProviderAdvertisementStatus.STARTED:
                break
            await asyncio.sleep(0.25)
        else:
            raise RuntimeError(f"GATT advertisement did not start: {provider.advertisement_status.name}")
        log(f"ADVERTISING service={SERVICE}")
        yield characteristic
    finally:
        provider.stop_advertising()
        characteristic.remove_read_requested(token)


async def stream(start, stop=None):
    async with advertise(start) as characteristic:
        while stop is None or time.monotonic() < stop:
            counter = int(time.monotonic() - start)
            if len(characteristic.subscribed_clients):
                results = await characteristic.notify_value_async(payload(counter))
                log(f"NOTIFY counter={counter} status={','.join(r.status.name for r in results)}")
            await asyncio.sleep(1)


async def main(args):
    adapter = await BluetoothAdapter.get_default_async()
    if adapter is None or not adapter.is_peripheral_role_supported:
        raise RuntimeError("A Bluetooth LE adapter with peripheral support is required.")
    radio = await adapter.get_radio_async()
    original = radio.state
    start = time.monotonic()
    try:
        await set_radio(radio, RadioState.ON)
        if args.interrupt_after:
            await stream(start, start + args.interrupt_after)
            await set_radio(radio, RadioState.OFF)
            log("RADIO_OFF")
            await asyncio.sleep(args.interrupt_for)
            await set_radio(radio, RadioState.ON)
            log("RADIO_ON")
            await asyncio.sleep(1)
        await stream(start, start + args.duration if args.duration else None)
    finally:
        await set_radio(radio, original)
        log(f"RADIO_RESTORED {original.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interrupt-after", type=int, default=0, help="turn the radio off after this many seconds")
    parser.add_argument("--interrupt-for", type=int, default=8, help="seconds to keep the radio off")
    parser.add_argument("--duration", type=int, default=0, help="total run time in seconds (0 waits for Ctrl+C)")
    args = parser.parse_args()
    if args.interrupt_after < 0 or args.interrupt_for < 1 or args.duration < 0:
        parser.error("use nonnegative times and a positive interruption length")
    if args.duration and args.interrupt_after and args.duration <= args.interrupt_after + args.interrupt_for:
        parser.error("--duration must leave time after the interruption")
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
