# firmware/fsr_output_reader.py
#
# CLI tool to read whatever the board is printing over serial.
# - Can auto-detect ESP32 / Feather ports on macOS
# - OR you can specify the port explicitly
# - You can also list all ports for debugging
#
# Usage:
#   source .venv/bin/activate
#   python firmware/fsr_output_reader.py               # auto-detect
#   python firmware/fsr_output_reader.py --list        # list all ports
#   python firmware/fsr_output_reader.py --port /dev/cu.usbserial-0001
#   python firmware/fsr_output_reader.py --port /dev/cu.usbmodem14301
#   python firmware/fsr_output_reader.py --port /dev/cu.usbmodem14101

import argparse
import time

import serial
import serial.tools.list_ports


def list_all_ports() -> None:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found at all.")
        return

    print("Available serial ports:\n")
    for p in ports:
        print(f"  {p.device}  |  {p.description}  |  {p.hwid}")
    print("")


def auto_detect_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    candidates = []

    for p in ports:
        dev = p.device
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        combo = f"{dev} {desc} {hwid}"

        # Filter out obvious Bluetooth virtual ports
        if "bluetooth" in combo:
            continue

        # Look for typical USB-serial / MCU hints
        score = 0
        if "usbserial" in combo or "usb modem" in combo or "usbmodem" in combo:
            score += 3
        if "cp210" in combo or "ch340" in combo or "wchusb" in combo:
            score += 2
        if "esp32" in combo or "feather" in combo or "arduino" in combo:
            score += 2
        if "usb" in combo:
            score += 1

        if score > 0:
            candidates.append((score, dev))

    if not candidates:
        raise RuntimeError(
            "No suitable serial ports found by auto-detect.\n"
            "Tip: run with --list to see what's available, or pass --port explicitly."
        )

    # Highest score first
    candidates.sort(reverse=True, key=lambda t: t[0])
    best_score, best_dev = candidates[0]
    print(f"Auto-detected port: {best_dev} (score={best_score})")
    return best_dev


class FSRReader:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 1.0) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def read_line(self) -> str | None:
        try:
            line = self.ser.readline().decode(errors="ignore").strip()
            return line or None
        except serial.SerialException:
            return None

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=None, help="Serial port (e.g. /dev/cu.usbserial-0001)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default 115200)")
    parser.add_argument("--list", action="store_true", help="List all serial ports and exit")
    args = parser.parse_args()

    if args.list:
        list_all_ports()
        return

    if args.port:
        port = args.port
        print(f"Using explicit port: {port}")
    else:
        port = auto_detect_port()

    reader = FSRReader(port=port, baud=args.baud)
    print(f"\nReading from {reader.port} at {reader.baud} baud (Ctrl+C to stop).\n")

    try:
        while True:
            line = reader.read_line()
            if line is not None:
                print(line)
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        reader.close()


if __name__ == "__main__":
    main()