import sys
import os
import asyncio
import threading
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont, QColor
from PyQt5.QtCore import QTimer, Qt
from bleak import BleakScanner, BleakClient
import winreg


class BluetoothBatteryMonitor:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.devices = {}
        self.tray_icon = None
        self.menu = None
        self.scanner_running = False
        self.loop = None
        self.thread = None
        
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
        
        self.refresh_action = QAction("Refresh Devices", self.app)
        self.refresh_action.triggered.connect(self.manual_refresh)
        self.menu.addAction(self.refresh_action)
        
        self.menu.addSeparator()
        
        self.devices_label = QAction("No devices found", self.app)
        self.devices_label.setEnabled(False)
        self.menu.addAction(self.devices_label)
        
        self.menu.addSeparator()
        
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
                devices = await BleakScanner.discover(timeout=5.0)
                
                for device in devices:
                    if device.name and device.address:
                        battery_level = await self.get_battery_level(device)
                        
                        if battery_level is not None:
                            self.devices[device.address] = {
                                'name': device.name,
                                'battery': battery_level,
                                'device': device
                            }
                
                await asyncio.sleep(10)
            except Exception as e:
                print(f"Error scanning devices: {e}")
                await asyncio.sleep(10)
    
    async def get_battery_level(self, device):
        try:
            async with BleakClient(device.address, timeout=5.0) as client:
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
            pass
        
        return None
    
    def update_device_list(self):
        for i in reversed(range(self.menu.actions().index(self.devices_label), 
                                len(self.menu.actions()) - 2)):
            action = self.menu.actions()[i]
            if action != self.devices_label:
                self.menu.removeAction(action)
        
        if self.devices:
            self.menu.removeAction(self.devices_label)
            
            for address, info in self.devices.items():
                device_text = f"{info['name']}: {info['battery']}%"
                device_action = QAction(device_text, self.app)
                device_action.setEnabled(False)
                self.menu.insertAction(self.quit_action, device_action)
            
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
                self.menu.insertAction(self.quit_action, self.devices_label)
            self.tray_icon.setIcon(self.create_battery_icon())
            self.tray_icon.setToolTip("Bluetooth Battery Monitor\nNo devices found")
    
    def manual_refresh(self):
        self.devices.clear()
        self.tray_icon.showMessage(
            "Bluetooth Battery Monitor",
            "Refreshing devices...",
            QSystemTrayIcon.Information,
            2000
        )
    
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
