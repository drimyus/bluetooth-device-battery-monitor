import sys
import os
import asyncio
import threading
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont, QColor
from PyQt5.QtCore import QTimer, Qt
from bleak import BleakScanner, BleakClient
import winreg
try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False


class BluetoothBatteryMonitor:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.devices = {}
        self.all_devices = {}
        self.tray_icon = None
        self.menu = None
        self.scanner_running = False
        self.loop = None
        self.thread = None
        self.scan_count = 0
        self.last_error = None
        
        self.setup_tray_icon()
        self.start_monitoring()
        
    def create_battery_icon(self, battery_level=None, device_name=""):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if battery_level is not None:
            if battery_level > 60:
                color = QColor(0, 200, 0)
            elif battery_level > 20:
                color = QColor(255, 165, 0)
            else:
                color = QColor(255, 0, 0)
            
            painter.setBrush(color)
            painter.setPen(Qt.black)
            painter.drawRect(10, 25, 40, 20)
            painter.drawRect(50, 30, 4, 10)
            
            fill_width = int(38 * battery_level / 100)
            painter.fillRect(11, 26, fill_width, 18, color)
            
            painter.setPen(Qt.white)
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)
            text = f"{battery_level}%"
            painter.drawText(12, 20, text)
        else:
            painter.setPen(Qt.gray)
            painter.setBrush(Qt.gray)
            painter.drawRect(10, 25, 40, 20)
            painter.drawRect(50, 30, 4, 10)
            
            painter.setPen(Qt.white)
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)
            painter.drawText(15, 20, "BT")
        
        painter.end()
        return QIcon(pixmap)
    
    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(self.create_battery_icon())
        self.tray_icon.setToolTip("Bluetooth Battery Monitor")
        
        self.menu = QMenu()
        
        self.status_action = QAction("Scanning...", self.app)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        
        self.menu.addSeparator()
        
        self.refresh_action = QAction("Refresh Devices", self.app)
        self.refresh_action.triggered.connect(self.manual_refresh)
        self.menu.addAction(self.refresh_action)
        
        self.show_all_action = QAction("Show All Devices", self.app)
        self.show_all_action.setCheckable(True)
        self.show_all_action.setChecked(False)
        self.show_all_action.triggered.connect(self.update_device_list)
        self.menu.addAction(self.show_all_action)
        
        self.menu.addSeparator()
        
        self.devices_label = QAction("No devices with battery found", self.app)
        self.devices_label.setEnabled(False)
        self.menu.addAction(self.devices_label)
        
        self.menu.addSeparator()
        
        self.help_action = QAction("Help / Troubleshooting", self.app)
        self.help_action.triggered.connect(self.show_help)
        self.menu.addAction(self.help_action)
        
        self.quit_action = QAction("Exit", self.app)
        self.quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(self.quit_action)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_device_list)
        self.update_timer.start(10000)
    
    def start_monitoring(self):
        self.scanner_running = True
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()
    
    def run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.scan_devices())
    
    async def scan_devices(self):
        while self.scanner_running:
            try:
                self.scan_count += 1
                print(f"[Scan #{self.scan_count}] Starting Bluetooth scan...")
                
                # Scan for Windows paired/connected Bluetooth devices
                await self.scan_windows_bluetooth()
                
                # Scan for BLE devices
                devices = await BleakScanner.discover(timeout=8.0)
                
                print(f"[Scan #{self.scan_count}] Found {len(devices)} BLE devices")
                
                for device in devices:
                    device_name = device.name if device.name else "Unknown"
                    print(f"  - {device_name} ({device.address})")
                    
                    if device.address:
                        self.all_devices[device.address] = {
                            'name': device_name,
                            'address': device.address,
                            'rssi': getattr(device, 'rssi', None),
                            'type': 'BLE'
                        }
                        
                        battery_level = await self.get_battery_level(device)
                        
                        if battery_level is not None:
                            print(f"    ✓ Battery: {battery_level}%")
                            self.devices[device.address] = {
                                'name': device_name,
                                'battery': battery_level,
                                'device': device
                            }
                        else:
                            print(f"    ✗ No battery service available")
                
                print(f"[Scan #{self.scan_count}] Total devices: {len(self.all_devices)}, with battery: {len(self.devices)}")
                self.last_error = None
                await asyncio.sleep(15)
            except Exception as e:
                error_msg = f"Error scanning devices: {e}"
                print(f"[Scan #{self.scan_count}] {error_msg}")
                self.last_error = str(e)
                await asyncio.sleep(15)
    
    async def scan_windows_bluetooth(self):
        """Scan for paired/connected Classic Bluetooth devices using Windows API"""
        try:
            if WMI_AVAILABLE:
                c = wmi.WMI()
                # Query Win32_PnPEntity for Bluetooth devices
                for device in c.Win32_PnPEntity():
                    if device.Name and 'bluetooth' in device.Name.lower():
                        # Skip Bluetooth adapters themselves
                        if 'adapter' in device.Name.lower() or 'radio' in device.Name.lower():
                            continue
                        
                        device_id = device.DeviceID if device.DeviceID else device.PNPDeviceID
                        if device_id:
                            print(f"  [Windows] {device.Name} (Status: {device.Status})")
                            self.all_devices[device_id] = {
                                'name': device.Name,
                                'address': device_id,
                                'rssi': None,
                                'type': 'Classic BT',
                                'status': device.Status
                            }
                            
                            # Try to get battery level from Windows
                            battery = self.get_windows_battery(device)
                            if battery is not None:
                                print(f"    ✓ Battery: {battery}%")
                                self.devices[device_id] = {
                                    'name': device.Name,
                                    'battery': battery,
                                    'device': device
                                }
            else:
                print("  [Windows] WMI not available, skipping Classic Bluetooth scan")
        except Exception as e:
            print(f"  [Windows] Error scanning Classic Bluetooth: {e}")
    
    def get_windows_battery(self, device):
        """Try to get battery level from Windows device properties"""
        try:
            if WMI_AVAILABLE:
                c = wmi.WMI()
                # Try to find battery information
                for battery in c.Win32_Battery():
                    if battery.EstimatedChargeRemaining:
                        return int(battery.EstimatedChargeRemaining)
        except:
            pass
        return None
    
    async def get_battery_level(self, device):
        try:
            async with BleakClient(device.address, timeout=10.0) as client:
                if client.is_connected:
                    battery_service_uuid = "0000180f-0000-1000-8000-00805f9b34fb"
                    battery_char_uuid = "00002a19-0000-1000-8000-00805f9b34fb"
                    
                    services = await client.get_services()
                    
                    for service in services:
                        if battery_service_uuid.lower() in str(service.uuid).lower():
                            for char in service.characteristics:
                                if battery_char_uuid.lower() in str(char.uuid).lower():
                                    value = await client.read_gatt_char(char.uuid)
                                    return int(value[0])
        except Exception as e:
            print(f"    Error reading battery from {device.name}: {e}")
        
        return None
    
    def update_device_list(self):
        for i in reversed(range(self.menu.actions().index(self.devices_label), 
                                len(self.menu.actions()) - 3)):
            action = self.menu.actions()[i]
            if action != self.devices_label:
                self.menu.removeAction(action)
        
        status_text = f"Scanned {self.scan_count} times | Found: {len(self.all_devices)} devices"
        if self.last_error:
            status_text += f" | Error: {self.last_error[:30]}..."
        self.status_action.setText(status_text)
        
        show_all = self.show_all_action.isChecked()
        
        if self.devices:
            self.menu.removeAction(self.devices_label)
            
            for address, info in self.devices.items():
                device_text = f"🔋 {info['name']}: {info['battery']}%"
                device_action = QAction(device_text, self.app)
                device_action.setEnabled(False)
                self.menu.insertAction(self.help_action, device_action)
            
            if show_all and self.all_devices:
                separator = QAction("─── All Discovered Devices ───", self.app)
                separator.setEnabled(False)
                self.menu.insertAction(self.help_action, separator)
                
                for address, info in self.all_devices.items():
                    if address not in self.devices:
                        device_type = info.get('type', 'Unknown')
                        rssi_text = f" ({info['rssi']} dBm)" if info.get('rssi') else ""
                        status_text = f" [{info.get('status', 'Unknown')}]" if 'status' in info else ""
                        device_text = f"📡 {info['name']} ({device_type}){rssi_text}{status_text}"
                        device_action = QAction(device_text, self.app)
                        device_action.setEnabled(False)
                        self.menu.insertAction(self.help_action, device_action)
            
            highest_battery_device = max(self.devices.values(), 
                                        key=lambda x: x['battery'])
            self.tray_icon.setIcon(
                self.create_battery_icon(
                    highest_battery_device['battery'],
                    highest_battery_device['name']
                )
            )
            self.tray_icon.setToolTip(
                f"Bluetooth Battery Monitor\n{highest_battery_device['name']}: "
                f"{highest_battery_device['battery']}%"
            )
        else:
            if self.devices_label not in self.menu.actions():
                self.menu.insertAction(self.help_action, self.devices_label)
            
            if show_all and self.all_devices:
                separator = QAction("─── All Discovered Devices ───", self.app)
                separator.setEnabled(False)
                self.menu.insertAction(self.help_action, separator)
                
                for address, info in self.all_devices.items():
                    device_type = info.get('type', 'Unknown')
                    rssi_text = f" ({info['rssi']} dBm)" if info.get('rssi') else ""
                    status_text = f" [{info.get('status', 'Unknown')}]" if 'status' in info else ""
                    device_text = f"📡 {info['name']} ({device_type}){rssi_text}{status_text}"
                    device_action = QAction(device_text, self.app)
                    device_action.setEnabled(False)
                    self.menu.insertAction(self.help_action, device_action)
            
            self.tray_icon.setIcon(self.create_battery_icon())
            tooltip = f"Bluetooth Battery Monitor\nScanned: {len(self.all_devices)} devices"
            if self.devices:
                tooltip += f"\nWith battery: {len(self.devices)}"
            else:
                tooltip += "\nNo battery-enabled devices found"
            self.tray_icon.setToolTip(tooltip)
    
    def manual_refresh(self):
        self.devices.clear()
        self.all_devices.clear()
        self.tray_icon.showMessage(
            "Bluetooth Battery Monitor",
            "Refreshing devices...",
            QSystemTrayIcon.Information,
            2000
        )
    
    def show_help(self):
        help_text = (
            "<h3>Bluetooth Battery Monitor</h3>"
            "<p><b>Troubleshooting:</b></p>"
            "<ol>"
            "<li><b>Pair your device:</b> Go to Windows Settings → Bluetooth & devices</li>"
            "<li><b>Connect your device:</b> Make sure it's actively connected (not just paired)</li>"
            "<li><b>Check compatibility:</b> Not all Bluetooth devices support battery reporting</li>"
            "<li><b>Enable 'Show All Devices':</b> See all discovered Bluetooth devices</li>"
            "</ol>"
            "<p><b>Supported Devices:</b></p>"
            "<ul>"
            "<li>Most modern Bluetooth earphones/headphones</li>"
            "<li>Devices with BLE Battery Service (GATT 0x180F)</li>"
            "</ul>"
            f"<p><b>Status:</b> Scanned {self.scan_count} times, found {len(self.all_devices)} devices total, "
            f"{len(self.devices)} with battery support.</p>"
        )
        
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Bluetooth Battery Monitor - Help")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(help_text)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec_()
    
    def quit_app(self):
        self.scanner_running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.tray_icon.hide()
        QApplication.quit()
    
    def run(self):
        return self.app.exec_()


def main():
    monitor = BluetoothBatteryMonitor()
    sys.exit(monitor.run())


if __name__ == "__main__":
    main()
