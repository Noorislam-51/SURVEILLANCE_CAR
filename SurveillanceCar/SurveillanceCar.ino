#include "esp_camera.h"
// ADD this line after #include "esp_camera.h"
#include "img_converters.h"
#include <Arduino.h>
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <vector>
#include <sstream>

struct MOTOR_PINS
{
  int pinEn;
  int pinIN1;
  int pinIN2;
};

std::vector<MOTOR_PINS> motorPins =
{
  {12, 13, 15}, // RIGHT MOTOR
  {12, 14, 2},  // LEFT MOTOR
};

#define LIGHT_PIN 4

#define UP 1
#define DOWN 2
#define LEFT 3
#define RIGHT 4
#define STOP 0

#define RIGHT_MOTOR 0
#define LEFT_MOTOR 1

#define FORWARD 1
#define BACKWARD -1

const int PWMFreq = 1000;
const int PWMResolution = 8;
const int PWMSpeedChannel = 2;
const int PWMLightChannel = 3;

// CAMERA PINS (AI THINKER ESP32-CAM)
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5

#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

const char* ssid = "MyWiFiCar";
const char* password = "12345678";

AsyncWebServer server(80);
AsyncWebSocket wsCamera("/Camera");
AsyncWebSocket wsCarInput("/CarInput");

uint32_t cameraClientId = 0;

// ================= HTML PAGE (UNCHANGED) =================
const char* htmlHomePage PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;text-align:center;background:#fff;}
.button{width:80px;height:80px;font-size:35px;background:black;color:red;border:none;border-radius:20px;margin:5px;}
.slider{width:250px;}
img{width:350px;border-radius:10px;}
</style>
</head>

<body>
<h2>ESP32-CAM WiFi Car</h2>
<img id="cameraImage">
<br><br>

<div>
<button class="button"
ontouchstart='sendButtonInput("MoveCar","1")'
ontouchend='sendButtonInput("MoveCar","0")'>↑</button>
</div>

<div>
<button class="button"
ontouchstart='sendButtonInput("MoveCar","3")'
ontouchend='sendButtonInput("MoveCar","0")'>←</button>

<button class="button"
ontouchstart='sendButtonInput("MoveCar","4")'
ontouchend='sendButtonInput("MoveCar","0")'>→</button>
</div>

<div>
<button class="button"
ontouchstart='sendButtonInput("MoveCar","2")'
ontouchend='sendButtonInput("MoveCar","0")'>↓</button>
</div>

<br>

<h3>Speed</h3>
<input type="range" min="0" max="255" value="180"
class="slider" id="Speed"
oninput='sendButtonInput("Speed",value)'>

<h3>Light</h3>
<input type="range" min="0" max="255" value="0"
class="slider" id="Light"
oninput='sendButtonInput("Light",value)'>

<script>
var websocketCamera, websocketCarInput;

function initCameraWebSocket(){
  websocketCamera = new WebSocket("ws://" + location.hostname + "/Camera");
  websocketCamera.binaryType = 'blob';

  websocketCamera.onmessage = function(event){
    document.getElementById("cameraImage").src =
      URL.createObjectURL(event.data);
  };

  websocketCamera.onclose = () => setTimeout(initCameraWebSocket,2000);
}

function initCarInputWebSocket(){
  websocketCarInput = new WebSocket("ws://" + location.hostname + "/CarInput");

  websocketCarInput.onopen = function(){
    sendButtonInput("Speed", Speed.value);
    sendButtonInput("Light", Light.value);
  };

  websocketCarInput.onclose = () => setTimeout(initCarInputWebSocket,2000);
}

function initWebSocket(){
  initCameraWebSocket();
  initCarInputWebSocket();
}

function sendButtonInput(key,value){
  websocketCarInput.send(key + "," + value);
}

window.onload = initWebSocket;
</script>

</body>
</html>
)rawliteral";

// ================= MOTOR CONTROL =================
void rotateMotor(int motorNumber, int motorDirection)
{
  if (motorDirection == FORWARD)
  {
    digitalWrite(motorPins[motorNumber].pinIN1, HIGH);
    digitalWrite(motorPins[motorNumber].pinIN2, LOW);
  }
  else if (motorDirection == BACKWARD)
  {
    digitalWrite(motorPins[motorNumber].pinIN1, LOW);
    digitalWrite(motorPins[motorNumber].pinIN2, HIGH);
  }
  else
  {
    digitalWrite(motorPins[motorNumber].pinIN1, LOW);
    digitalWrite(motorPins[motorNumber].pinIN2, LOW);
  }
}

void moveCar(int inputValue)
{
  switch(inputValue)
  {
    case UP:
      rotateMotor(RIGHT_MOTOR, FORWARD);
      rotateMotor(LEFT_MOTOR, FORWARD);
      break;

    case DOWN:
      rotateMotor(RIGHT_MOTOR, BACKWARD);
      rotateMotor(LEFT_MOTOR, BACKWARD);
      break;

    case LEFT:
      rotateMotor(RIGHT_MOTOR, FORWARD);
      rotateMotor(LEFT_MOTOR, BACKWARD);
      break;

    case RIGHT:
      rotateMotor(RIGHT_MOTOR, BACKWARD);
      rotateMotor(LEFT_MOTOR, FORWARD);
      break;

    default:
      rotateMotor(RIGHT_MOTOR, STOP);
      rotateMotor(LEFT_MOTOR, STOP);
      break;
  }
}

// ================= CAMERA FIXED =================
void setupCamera()
{
  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;

  // 🔥 FIX: safe start mode
  config.pixel_format = PIXFORMAT_RGB565;

  if(psramFound())
  {
    Serial.println("PSRAM FOUND");
    config.frame_size = FRAMESIZE_QQVGA;
    config.fb_count = 2;
  }
  else
  {
    Serial.println("PSRAM NOT FOUND");
    config.frame_size = FRAMESIZE_QQVGA;
    config.fb_count = 1;
  }

  config.jpeg_quality = 12;

  esp_err_t err = esp_camera_init(&config);

  if(err != ESP_OK)
  {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return;
  }

  Serial.println("Camera initialized successfully");
}

// // ================= CAMERA STREAM =================
// void sendCameraPicture()
// {
//   if(cameraClientId == 0) return;

//   camera_fb_t * fb = esp_camera_fb_get();
//   if(!fb) return;

//   wsCamera.binary(cameraClientId, (const char*)fb->buf, fb->len);

//   esp_camera_fb_return(fb);
// }
// ✅ FIXED CODE — converts to JPEG first, then sends
void sendCameraPicture()
{
  if(cameraClientId == 0) return;

  camera_fb_t *fb = esp_camera_fb_get();
  if(!fb) return;

  uint8_t *jpg_buf = NULL;
  size_t   jpg_len = 0;

  // Convert RGB565 → JPEG in software
  bool ok = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
  esp_camera_fb_return(fb);   // return buffer immediately

  if(!ok || jpg_buf == NULL){
    Serial.println("JPEG conversion failed");
    if(jpg_buf) free(jpg_buf);
    return;
  }

  // Now send JPEG — browser can display this
  wsCamera.binary(cameraClientId, (const char*)jpg_buf, jpg_len);
  free(jpg_buf);   // free memory after sending
}

// ================= WEB SOCKET =================
void onCarInputWebSocketEvent(AsyncWebSocket *server,
AsyncWebSocketClient *client,
AwsEventType type,
void *arg,
uint8_t *data,
size_t len)
{
  if(type == WS_EVT_DATA)
  {
    AwsFrameInfo *info = (AwsFrameInfo*)arg;

    if(info->final && info->len == len && info->opcode == WS_TEXT)
    {
      std::string msg((char*)data, len);
      std::istringstream ss(msg);

      std::string key, value;
      getline(ss, key, ',');
      getline(ss, value, ',');

      int val = atoi(value.c_str());

      if(key == "MoveCar") moveCar(val);
      else if(key == "Speed") ledcWrite(PWMSpeedChannel, val);
      else if(key == "Light") ledcWrite(PWMLightChannel, val);
    }
  }

  if(type == WS_EVT_DISCONNECT)
  {
    moveCar(STOP);
  }
}

void onCameraWebSocketEvent(AsyncWebSocket *server,
AsyncWebSocketClient *client,
AwsEventType type,
void *arg,
uint8_t *data,
size_t len)
{
  if(type == WS_EVT_CONNECT)
    cameraClientId = client->id();
  else if(type == WS_EVT_DISCONNECT)
    cameraClientId = 0;
}

// ================= PIN SETUP =================
void setUpPinModes()
{
  ledcSetup(PWMSpeedChannel, PWMFreq, PWMResolution);
  ledcSetup(PWMLightChannel, PWMFreq, PWMResolution);

  for(auto &m : motorPins)
  {
    pinMode(m.pinEn, OUTPUT);
    pinMode(m.pinIN1, OUTPUT);
    pinMode(m.pinIN2, OUTPUT);

    ledcAttachPin(m.pinEn, PWMSpeedChannel);
  }

  pinMode(LIGHT_PIN, OUTPUT);
  ledcAttachPin(LIGHT_PIN, PWMLightChannel);

  moveCar(STOP);
}

// ================= SETUP =================
void setup()
{
  Serial.begin(115200);

  setupCamera();
  setUpPinModes();

  WiFi.softAP(ssid, password);

  Serial.println("WiFi Started");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send_P(200, "text/html", htmlHomePage);
  });

  wsCamera.onEvent(onCameraWebSocketEvent);
  wsCarInput.onEvent(onCarInputWebSocketEvent);

  server.addHandler(&wsCamera);
  server.addHandler(&wsCarInput);

  server.begin();
}

// ================= LOOP =================
void loop()
{
  wsCamera.cleanupClients();
  wsCarInput.cleanupClients();

  sendCameraPicture();
}