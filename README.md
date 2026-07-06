# ESP32-CAM WiFi Surveillance Car

A WiFi-controlled robotic car built using the ESP32-CAM and RHYX M21-45 camera module. The car creates its own WiFi hotspot, allowing users to connect through a smartphone or laptop browser, view a live camera feed, control movement, adjust speed, and control an onboard LED light.

## Features

- Live camera streaming over WiFi
- Browser-based control interface
- Forward, Backward, Left, and Right movement
- Adjustable motor speed control
- LED brightness control
- No mobile app required
- ESP32 SoftAP mode (creates its own WiFi network)
- Real-time communication using WebSockets

## Hardware Components

- AI Thinker ESP32-CAM
- RHYX M21-45 Camera Module
- L298N Motor Driver
- 2 DC Gear Motors
- Robot Chassis
- Battery Pack
- LED Light
- Jumper Wires

## Camera Information

### RHYX M21-45 Camera Module

This project uses the **RHYX M21-45 (GC2145-compatible)** camera sensor instead of the commonly used OV2640.

### Important Note

The RHYX M21-45 camera does not support native JPEG output. Instead, it captures frames in RGB565 format. To display images in a web browser, frames are converted from RGB565 to JPEG using the `frame2jpg()` function before transmission. This modification is essential for successful video streaming.

### Camera Configuration Used

```cpp
config.pixel_format = PIXFORMAT_RGB565;
config.frame_size   = FRAMESIZE_QQVGA;
config.fb_count     = 2;
```

## Motor Connections

### Right Motor

| ESP32-CAM | Motor Driver |
| --------- | ------------ |
| GPIO 13   | IN1          |
| GPIO 15   | IN2          |
| GPIO 12   | ENA          |

### Left Motor

| ESP32-CAM | Motor Driver |
| --------- | ------------ |
| GPIO 14   | IN3          |
| GPIO 2    | IN4          |
| GPIO 12   | ENB          |

### LED Light

| ESP32-CAM | Component |
| --------- | --------- |
| GPIO 4    | LED       |

## Camera Pin Mapping

The project uses the default AI Thinker ESP32-CAM camera configuration.

| Camera Signal | GPIO    |
| ------------- | ------- |
| XCLK          | GPIO 0  |
| SIOD          | GPIO 26 |
| SIOC          | GPIO 27 |
| Y9            | GPIO 35 |
| Y8            | GPIO 34 |
| Y7            | GPIO 39 |
| Y6            | GPIO 36 |
| Y5            | GPIO 21 |
| Y4            | GPIO 19 |
| Y3            | GPIO 18 |
| Y2            | GPIO 5  |
| VSYNC         | GPIO 25 |
| HREF          | GPIO 23 |
| PCLK          | GPIO 22 |

## Software Requirements

- Arduino IDE
- ESP32 Board Package
- ESPAsyncWebServer
- AsyncTCP
- ESP32 Camera Library

## Arduino IDE Setup

### Install ESP32 Board Package

Add the following URL to **Additional Board Manager URLs**:

```text
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

Then install:

- **ESP32** by Espressif Systems

### Install Required Libraries

- ESPAsyncWebServer
- AsyncTCP
- ESP32 Camera Library

## Upload Settings

Select the following options:

- **Board:** AI Thinker ESP32-CAM
- **PSRAM:** Enabled
- **Partition Scheme:** Huge APP (3MB No OTA)

## WiFi Access Point

The ESP32 creates its own WiFi network.

```text
SSID:     MyWiFiCar
Password: 12345678
```

## How to Run

1. Upload the code to ESP32-CAM.
2. Open Serial Monitor (115200 baud).
3. Power the robot car.
4. Connect your phone or laptop to the network:

   ```text
   MyWiFiCar
   ```

5. Enter the password:

   ```text
   12345678
   ```

6. Open a browser.
7. Visit the IP address shown in Serial Monitor.
8. Control the car and view the live camera stream.

## Web Interface

### Movement Controls

| Button | Function      |
| ------ | ------------- |
| ↑      | Move Forward  |
| ↓      | Move Backward |
| ←      | Turn Left     |
| →      | Turn Right    |

### Sliders

- Speed Control (0–255)
- Light Brightness Control (0–255)

## Project Structure

```text
ESP32-CAM-WIFI-CAR/
│
├── Camera Initialization
├── Motor Control
├── PWM Speed Control
├── LED Control
├── WebSocket Communication
├── Web Server
└── Live Video Streaming
```

## Challenges Solved

- RHYX M21-45 camera compatibility
- RGB565 to JPEG conversion
- Real-time WebSocket communication
- Simultaneous motor control and video streaming
- Browser-based control interface

## Future Improvements

- Object Tracking
- Face Detection
- Obstacle Avoidance
- Line Following
- Mobile Application
- Cloud Video Streaming
- Voice Control

## Author

**Noor Islam**
B.Tech Electronics (VLSI Design & Technology)
Jamia Millia Islamia

## License

This project is released under the MIT License and can be used for educational and personal projects.
# SURVEILLANCE_CAR
