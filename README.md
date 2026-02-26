# Bluetooth Battery Monitor for Windows 10

A system tray application that monitors battery levels of connected Bluetooth devices (e.g., earphones, headphones) on Windows 10.

## Features

- **System Tray Icon**: Displays battery level directly in the system tray
- **Real-time Monitoring**: Automatically scans for Bluetooth devices every 10 seconds
- **Battery Status**: Shows battery percentage for all connected Bluetooth devices
- **Visual Indicators**: Color-coded battery icon (green > 60%, orange > 20%, red ≤ 20%)
- **Context Menu**: Right-click tray icon to see all devices and their battery levels
- **Manual Refresh**: Force refresh device list on demand

## Requirements

- Windows 10 or later
- Python 3.8 or higher
- Bluetooth adapter

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python bluetooth_battery_monitor.py
```

## Building Executable

To create a standalone executable:

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build the executable:
```bash
pyinstaller build.spec
```

The executable will be created in the `dist` folder.

## Usage

1. Run the application (it will minimize to system tray)
2. Right-click the tray icon to see connected Bluetooth devices
3. Battery levels are displayed next to each device name
4. The tray icon shows the battery level of the device with the highest battery
5. Click "Refresh Devices" to manually scan for devices
6. Click "Exit" to close the application

## Supported Devices

The app works with Bluetooth devices that support the Battery Service (BLE GATT service UUID 0x180F), including:
- Bluetooth earphones
- Bluetooth headphones
- Bluetooth speakers
- Other BLE devices with battery reporting

## Troubleshooting

- **No devices found**: Ensure Bluetooth is enabled and devices are paired and connected
- **Permission errors**: Run the application as administrator if needed
- **Scanning issues**: Some devices may not report battery levels via standard BLE services

## Technical Details

- Uses BLE (Bluetooth Low Energy) GATT Battery Service
- Scans for devices every 10 seconds
- Updates tray icon and menu dynamically
- Runs in background with minimal resource usage
