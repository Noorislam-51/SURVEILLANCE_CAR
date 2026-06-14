// #include "esp_camera.h"
// #include <Arduino.h>
// #include <WiFi.h>
// #include <AsyncTCP.h>
// #include <ESPAsyncWebServer.h>
// #include <vector>
// #include <sstream>

// struct MOTOR_PINS {
//   int pinEn, pinIN1, pinIN2;
// };

// std::vector<MOTOR_PINS> motorPins = {
//   {12, 13, 15}, // RIGHT MOTOR
//   {12, 14,  2}, // LEFT MOTOR
// };

// #define LIGHT_PIN 4
// #define UP 1
// #define DOWN 2
// #define LEFT 3
// #define RIGHT 4
// #define STOP 0
// #define RIGHT_MOTOR 0
// #define LEFT_MOTOR 1
// #define FORWARD 1
// #define BACKWARD -1

// const int PWMFreq        = 1000;
// const int PWMResolution  = 8;
// const int PWMSpeedChannel = 2;
// const int PWMLightChannel = 3;

// // CAMERA PINS (AI THINKER)
// #define PWDN_GPIO_NUM   32
// #define RESET_GPIO_NUM  -1
// #define XCLK_GPIO_NUM    0
// #define SIOD_GPIO_NUM   26
// #define SIOC_GPIO_NUM   27
// #define Y9_GPIO_NUM     35
// #define Y8_GPIO_NUM     34
// #define Y7_GPIO_NUM     39
// #define Y6_GPIO_NUM     36
// #define Y5_GPIO_NUM     21
// #define Y4_GPIO_NUM     19
// #define Y3_GPIO_NUM     18
// #define Y2_GPIO_NUM      5
// #define VSYNC_GPIO_NUM  25
// #define HREF_GPIO_NUM   23
// #define PCLK_GPIO_NUM   22

// const char* ssid     = "MyWiFiCar";
// const char* password = "12345678";

// AsyncWebServer server(80);
// AsyncWebSocket wsCamera("/Camera");
// AsyncWebSocket wsCarInput("/CarInput");
// uint32_t cameraClientId = 0;

// // ------------------------------------------------------------------
// // HTML page stored in flash (PROGMEM)
// // Uses <canvas> + JS to decode raw RGB565 frames from WebSocket
// // ------------------------------------------------------------------
// const char htmlHomePage[] PROGMEM =
// "<!DOCTYPE html>"
// "<html><head>"
// "<meta name='viewport' content='width=device-width, initial-scale=1'>"
// "<style>"
// "body{font-family:Arial;text-align:center;background:#fff;}"
// ".btn{width:80px;height:80px;font-size:35px;background:#000;color:red;"
// "     border:none;border-radius:20px;margin:5px;}"
// ".slider{width:250px;}"
// "canvas{width:320px;border-radius:10px;display:block;margin:auto;}"
// "</style></head><body>"
// "<h2>ESP32-CAM WiFi Car</h2>"
// "<canvas id='cam' width='320' height='240'></canvas><br>"
// "<div>"
// "  <button class='btn' ontouchstart='send(\"MoveCar\",\"1\")' ontouchend='send(\"MoveCar\",\"0\")'>&#8593;</button>"
// "</div><div>"
// "  <button class='btn' ontouchstart='send(\"MoveCar\",\"3\")' ontouchend='send(\"MoveCar\",\"0\")'>&#8592;</button>"
// "  <button class='btn' ontouchstart='send(\"MoveCar\",\"4\")' ontouchend='send(\"MoveCar\",\"0\")'>&#8594;</button>"
// "</div><div>"
// "  <button class='btn' ontouchstart='send(\"MoveCar\",\"2\")' ontouchend='send(\"MoveCar\",\"0\")'>&#8595;</button>"
// "</div><br>"
// "<h3>Speed</h3>"
// "<input type='range' min='0' max='255' value='180' class='slider' id='spd' oninput='send(\"Speed\",value)'>"
// "<h3>Light</h3>"
// "<input type='range' min='0' max='255' value='0' class='slider' id='lgt' oninput='send(\"Light\",value)'>"
// "<script>"
// "var canvas=document.getElementById('cam');"
// "var ctx=canvas.getContext('2d');"
// "var wsCam,wsCtrl;"
// "function drawRGB565(buf){"
// "  var d=new Uint8Array(buf);"
// "  var img=ctx.createImageData(320,240);"
// "  for(var i=0;i<320*240;i++){"
// "    var hi=d[i*2],lo=d[i*2+1];"
// "    var px=(hi<<8)|lo;"
// "    img.data[i*4]  =((px>>11)&0x1F)<<3;"
// "    img.data[i*4+1]=((px>>5)&0x3F)<<2;"
// "    img.data[i*4+2]=(px&0x1F)<<3;"
// "    img.data[i*4+3]=255;"
// "  }"
// "  ctx.putImageData(img,0,0);"
// "}"
// "function initCam(){"
// "  wsCam=new WebSocket('ws://'+location.hostname+'/Camera');"
// "  wsCam.binaryType='arraybuffer';"
// "  wsCam.onmessage=function(e){drawRGB565(e.data);};"
// "  wsCam.onclose=function(){setTimeout(initCam,2000);};"
// "}"
// "function initCtrl(){"
// "  wsCtrl=new WebSocket('ws://'+location.hostname+'/CarInput');"
// "  wsCtrl.onopen=function(){"
// "    send('Speed',document.getElementById('spd').value);"
// "    send('Light',document.getElementById('lgt').value);"
// "  };"
// "  wsCtrl.onclose=function(){setTimeout(initCtrl,2000);};"
// "}"
// "function send(k,v){wsCtrl.send(k+','+v);}"
// "window.onload=function(){initCam();initCtrl();};"
// "</script></body></html>";

// // ------------------------------------------------------------------
// // Motor control
// // ------------------------------------------------------------------
// void rotateMotor(int motor, int dir) {
//   if      (dir == FORWARD)  { digitalWrite(motorPins[motor].pinIN1, HIGH); digitalWrite(motorPins[motor].pinIN2, LOW);  }
//   else if (dir == BACKWARD) { digitalWrite(motorPins[motor].pinIN1, LOW);  digitalWrite(motorPins[motor].pinIN2, HIGH); }
//   else                      { digitalWrite(motorPins[motor].pinIN1, LOW);  digitalWrite(motorPins[motor].pinIN2, LOW);  }
// }

// void moveCar(int v) {
//   switch(v) {
//     case UP:    rotateMotor(RIGHT_MOTOR, FORWARD);  rotateMotor(LEFT_MOTOR, FORWARD);  break;
//     case DOWN:  rotateMotor(RIGHT_MOTOR, BACKWARD); rotateMotor(LEFT_MOTOR, BACKWARD); break;
//     case LEFT:  rotateMotor(RIGHT_MOTOR, FORWARD);  rotateMotor(LEFT_MOTOR, BACKWARD); break;
//     case RIGHT: rotateMotor(RIGHT_MOTOR, BACKWARD); rotateMotor(LEFT_MOTOR, FORWARD);  break;
//     default:    rotateMotor(RIGHT_MOTOR, STOP);     rotateMotor(LEFT_MOTOR, STOP);     break;
//   }
// }

// // ------------------------------------------------------------------
// // WebSocket handlers
// // ------------------------------------------------------------------
// void handleRoot(AsyncWebServerRequest *request) {
//   request->send_P(200, "text/html", htmlHomePage);
// }

// void onCarInputWSEvent(AsyncWebSocket *s, AsyncWebSocketClient *c,
//                        AwsEventType type, void *arg, uint8_t *data, size_t len) {
//   if (type == WS_EVT_DATA) {
//     AwsFrameInfo *info = (AwsFrameInfo*)arg;
//     if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
//       std::string msg; msg.assign((char*)data, len);
//       std::istringstream ss(msg);
//       std::string key, val;
//       getline(ss, key, ','); getline(ss, val, ',');
//       int v = atoi(val.c_str());
//       if      (key == "MoveCar") moveCar(v);
//       else if (key == "Speed")   ledcWrite(PWMSpeedChannel, v);
//       else if (key == "Light")   ledcWrite(PWMLightChannel, v);
//     }
//   } else if (type == WS_EVT_DISCONNECT) {
//     moveCar(STOP);
//     ledcWrite(PWMLightChannel, 0);
//   }
// }

// void onCameraWSEvent(AsyncWebSocket *s, AsyncWebSocketClient *c,
//                      AwsEventType type, void *arg, uint8_t *data, size_t len) {
//   if      (type == WS_EVT_CONNECT)    cameraClientId = c->id();
//   else if (type == WS_EVT_DISCONNECT) cameraClientId = 0;
// }

// // ------------------------------------------------------------------
// // Camera setup  — FIX 1: RGB565  FIX 2: sccb pins  FIX 3: PSRAM
// // ------------------------------------------------------------------
// void setupCamera() {
//   camera_config_t config;
//   config.ledc_channel = LEDC_CHANNEL_0;
//   config.ledc_timer   = LEDC_TIMER_0;
//   config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
//   config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
//   config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
//   config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
//   config.pin_xclk      = XCLK_GPIO_NUM;
//   config.pin_pclk      = PCLK_GPIO_NUM;
//   config.pin_vsync     = VSYNC_GPIO_NUM;
//   config.pin_href      = HREF_GPIO_NUM;
//   config.pin_sccb_sda  = SIOD_GPIO_NUM;  // FIX 2: was pin_sscb_sda (typo)
//   config.pin_sccb_scl  = SIOC_GPIO_NUM;  // FIX 2: was pin_sscb_scl (typo)
//   config.pin_pwdn      = PWDN_GPIO_NUM;
//   config.pin_reset     = RESET_GPIO_NUM;
//   config.xclk_freq_hz  = 20000000;
//   config.pixel_format  = PIXFORMAT_RGB565; // FIX 1: sensor doesn't support JPEG
//   config.frame_size    = FRAMESIZE_QVGA;   // 320x240
//   config.grab_mode     = CAMERA_GRAB_WHEN_EMPTY;
//   config.fb_count      = 1;

//   if (psramFound()) {
//     Serial.println("PSRAM FOUND");
//     config.fb_location = CAMERA_FB_IN_PSRAM; // FIX 3: prevents malloc failure
//     config.fb_count    = 2;
//   } else {
//     Serial.println("PSRAM NOT FOUND - using DRAM");
//     config.fb_location = CAMERA_FB_IN_DRAM;
//     config.frame_size  = FRAMESIZE_QQVGA;
//   }

//   esp_err_t err = esp_camera_init(&config);
//   if (err != ESP_OK) {
//     Serial.printf("Camera init failed: 0x%x\n", err);
//     return;
//   }
//   Serial.println("Camera initialized successfully!");
// }

// // ------------------------------------------------------------------
// // Send one frame
// // ------------------------------------------------------------------
// void sendCameraPicture() {
//   if (cameraClientId == 0) return;
//   camera_fb_t *fb = esp_camera_fb_get();
//   if (!fb) { Serial.println("Capture failed"); return; }
//   wsCamera.binary(cameraClientId, (const char*)fb->buf, fb->len);
//   esp_camera_fb_return(fb);
//   while (true) {
//     AsyncWebSocketClient *cp = wsCamera.client(cameraClientId);
//     if (!cp || !cp->queueIsFull()) break;
//     delay(1);
//   }
// }

// // ------------------------------------------------------------------
// // Pin / PWM setup
// // ------------------------------------------------------------------
// void setUpPinModes() {
//   ledcSetup(PWMSpeedChannel, PWMFreq, PWMResolution);
//   ledcSetup(PWMLightChannel, PWMFreq, PWMResolution);
//   for (int i = 0; i < (int)motorPins.size(); i++) {
//     pinMode(motorPins[i].pinEn,  OUTPUT);
//     pinMode(motorPins[i].pinIN1, OUTPUT);
//     pinMode(motorPins[i].pinIN2, OUTPUT);
//     ledcAttachPin(motorPins[i].pinEn, PWMSpeedChannel);
//   }
//   moveCar(STOP);
//   pinMode(LIGHT_PIN, OUTPUT);
//   ledcAttachPin(LIGHT_PIN, PWMLightChannel);
// }

// // ------------------------------------------------------------------
// // Setup & loop
// // ------------------------------------------------------------------
// void setup() {
//   Serial.begin(115200);
//   setupCamera();
//   setUpPinModes();

//   WiFi.softAP(ssid, password);
//   Serial.println("WiFi AP Started");
//   Serial.print("Open Browser: http://");
//   Serial.println(WiFi.softAPIP());

//   server.on("/", HTTP_GET, handleRoot);
//   wsCamera.onEvent(onCameraWSEvent);
//   server.addHandler(&wsCamera);
//   wsCarInput.onEvent(onCarInputWSEvent);
//   server.addHandler(&wsCarInput);
//   server.begin();
//   Serial.println("Server Started");
// }

// void loop() {
//   wsCamera.cleanupClients();
//   wsCarInput.cleanupClients();
//   sendCameraPicture();

//   static unsigned long lastPrint = 0;
//   if (millis() - lastPrint > 3000) {
//     lastPrint = millis();
//     Serial.printf("PSRAM Total: %d | Free: %d\n", ESP.getPsramSize(), ESP.getFreePsram());
//   }
// }