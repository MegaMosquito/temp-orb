#
# Code for my temperature orb
#
# Written by Glen Darling, Sept. 2020.
#

from datetime import datetime
import json
import requests
import signal
import subprocess
import sys
import threading
import time

# LEDs are dimmed before MORNING_HOUR and after EVENING_HOUR (24hr clock!)
MORNING_HOUR = 6
EVENING_HOUR = 20


# This code connects to the central PurpleAir cloud APIs
# Example:
#   curl --header "X-API-Key: *****" https://api.purpleair.com/v1/keys
#   curl --header "X-API-Key: *****" https://api.purpleair.com/v1/sensors/*****
# Full API documentation:
#   https://api.purpleair.com
# More info:
#    https://community.purpleair.com/t/making-api-calls-with-the-purpleair-api/180
#
# API Details:
PURPLE_AIR_SENSOR_URL       = 'https://api.purpleair.com/v1/sensors/'
PURPLE_AIR_API_KEY_HEADER   = 'X-API-Key'
#
# My credentials (edit these to contain your own values):
MY_PURPLE_AIR_READ_API_KEY  = 'YOUR KEY GOES HERE'
MY_PURPLE_AIR_WRITE_API_KEY = 'YOUR KEY GOES HERE'
#
# My outdoor sensor index (edit this to contain your own index number):
MY_PURPLE_AIR_OUTDOOR_INDEX = 12345

# URL for my homemade indoor "PicoWAQI" AQI/temperature/pressure sensor
MY_INDOOR_SENSOR_URL = 'http://192.168.123.92/json'

# Import the required libraries
import board
import neopixel

# A global to indicate the input pin number connected to the NeoPixels
neopixel_pin = board.D18

# A global to indicate the number of NeoPixels that are connected
neopixel_count = 12

# The global array of neopixels
neopixels = None

# Initialize the NeoPixels
neopixels = neopixel.NeoPixel(neopixel_pin, neopixel_count)

# Globals to contain the monitored temperature values
g_inside = -1.0
g_outside = -1.0

# Global to keep the threads looping
keep_on_swimming = True

# Tolerate for this many fails before marking sensor offline
FAIL_COUNT_TOLERANCE = 8

# Color to show when offline
OFFLINE_COLOR = (0, 0, 255)

# Debug flags
DEBUG_TEMPS = False
DEBUG_INSIDE = False
DEBUG_OUTSIDE = False
DEBUG_API = False
DEBUG_MAIN_LOOP = False
DEBUG_DIMMING = False
DEBUG_SIGNAL = False

# Debug print
def debug(flag, str):
  if flag:
    print(str)

# Invoke the PurpleAir "sensors" API for my sensor with my API key
def get_sensor(i, t):
  url = PURPLE_AIR_SENSOR_URL + str(i)
  headers = {
    PURPLE_AIR_API_KEY_HEADER:MY_PURPLE_AIR_READ_API_KEY,
    'Content-Type':'json'
  }
  debug(DEBUG_API, 'API request: "' + url + '"')
  r = requests.get(url, headers=headers, timeout=t)
  if (200 == r.status_code):
    debug(DEBUG_API, '--> [success]')
  else:
    debug(DEBUG_API, '--> [error] status code: ' + r.status_code)
  return r

# Thread that monitors inside temperature and updates the `g_inside` global
INSIDE_REQUEST_TIMEOUT_SEC = 30
SLEEP_BETWEEN_INSIDE_TEMP_CHECKS_SEC = 15
g_inside_fails = 0
class InsideThread(threading.Thread):
  def run(self):
    global g_inside
    global g_inside_fails
    headers = {}
    debug(DEBUG_INSIDE, "Inside temperature monitor thread started!")
    while keep_on_swimming:
      try:
        debug(DEBUG_INSIDE, ('INSIDE: t/o=%d' % (INSIDE_REQUEST_TIMEOUT_SEC)))
        r = requests.get(MY_INDOOR_SENSOR_URL, headers=headers, timeout=INSIDE_REQUEST_TIMEOUT_SEC)
        if 200 == r.status_code:
          debug(DEBUG_INSIDE, '--> "inside" [success]')
          g_inside_fails = 0
          j = r.json()
          debug(DEBUG_INSIDE, '--> "inside" [' + json.dumps(j) + ']')
          g_inside = float(j['temperature']['fahrenheit'])
          debug(DEBUG_INSIDE or DEBUG_TEMPS, ('*** INSIDE == %f ***' % (g_inside)))
        else:
          debug(DEBUG_INSIDE, '--> "inside" [failure] status code: ' + r.status_code)
          g_inside_fails += 1
      except requests.exceptions.Timeout:
        debug(DEBUG_INSIDE, '--> "inside" [timeout]')
        g_inside_fails += 1
      except:
        debug(DEBUG_INSIDE, '--> "inside" [exception]')
        g_inside_fails += 1
      if g_inside_fails > FAIL_COUNT_TOLERANCE:
        g_inside = -1
      time.sleep(SLEEP_BETWEEN_INSIDE_TEMP_CHECKS_SEC)
    debug(DEBUG_SIGNAL, 'Exited inside thread.')

# Thread that monitors outside temperature and updates the `g_outside` global
OUTSIDE_REQUEST_TIMEOUT_SEC = 30
SLEEP_BETWEEN_OUTSIDE_TEMP_CHECKS_SEC = 15
g_outside_fails = 0
class OutsideThread(threading.Thread):
  def run(self):
    global g_outside
    global g_outside_fails
    debug(DEBUG_OUTSIDE, "Outside temperature monitor thread started!")
    while keep_on_swimming:
      try:
        debug(DEBUG_OUTSIDE, ('OUTSIDE: t/o=%d' % (OUTSIDE_REQUEST_TIMEOUT_SEC)))
        r = get_sensor(MY_PURPLE_AIR_OUTDOOR_INDEX, OUTSIDE_REQUEST_TIMEOUT_SEC)
        if 200 == r.status_code:
          debug(DEBUG_OUTSIDE, '--> "inside" [success]') 
          g_outside_fails = 0
          j = r.json()
          g_outside = float(j['sensor']['temperature'])
          debug(DEBUG_OUTSIDE or DEBUG_TEMPS, ('*** OUTSIDE == %f ***' % (g_outside)))
        else:
          debug(DEBUG_OUTSIDE, '--> "inside" [failure]') 
          g_outside_fails += 1
      except requests.exceptions.Timeout:
        debug(DEBUG_OUTSIDE, '--> "inside" [timeout]') 
        g_outside_fails += 1
      except:
        debug(DEBUG_OUTSIDE, '--> "inside" [exception]') 
        g_outside_fails += 1
      if g_outside_fails > FAIL_COUNT_TOLERANCE:
        g_outside = -1
      time.sleep(SLEEP_BETWEEN_OUTSIDE_TEMP_CHECKS_SEC)
    debug(DEBUG_SIGNAL, 'Exited outside thread.')

# Given a pair of inside/outside temperatures, return an RGB color
def temps_to_rgb(inside, outside):
  if inside < 0 or outside < 0:
    return OFFLINE_COLOR
  if inside >= outside:
    return (0, 255, 0)
  else:
    return (255, 0, 0)

# Main program (to start the web server thread)
if __name__ == '__main__':

  def signal_handler(signum, frame):
    global keep_on_swimming
    debug(DEBUG_SIGNAL, 'Signal received!')
    keep_on_swimming = False
    time.sleep(5)
    sys.exit(0)
  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGQUIT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  # Start the thread that checks the inside temperature from the sensor
  inside_check = InsideThread()
  inside_check.start()

  # Start the thread that checks the outside temperature from the sensor
  outside_check = OutsideThread()
  outside_check.start()

  # Loop forever checking global temperatures and setting NeoPixels
  SLEEP_BETWEEN_NEOPIXEL_UPDATES_SEC = 15
  debug(DEBUG_MAIN_LOOP, "Main loop is starting...")
  while keep_on_swimming:
    rgb = temps_to_rgb(g_inside, g_outside)
    debug(DEBUG_DIMMING, ('      Original:      (%3d,%3d,%3d)' % (rgb[0], rgb[1], rgb[2])))
    # Dim all the normal colors (NeoPixels are very bright!)
    if rgb != OFFLINE_COLOR:
      r = rgb[0]
      g = rgb[1]
      b = rgb[2]
      rgb = (int(r / 8), int(g / 8), int(b / 8))
      debug(DEBUG_DIMMING, ('      Dimmed:        (%3d,%3d,%3d)' % (rgb[0], rgb[1], rgb[2])))
    # Further dim in the evening/night
    now = datetime.now()
    hr = int(now.strftime("%H"))
    if hr < MORNING_HOUR or hr > EVENING_HOUR:
      rgb = (int(rgb[0] / 3), int(rgb[1] / 3), int(rgb[2] / 3))
      debug(DEBUG_DIMMING, ('      Night dimmed:  (%3d,%3d,%3d)' % (rgb[0], rgb[1], rgb[2])))
    neopixels.fill(rgb)
    debug(DEBUG_MAIN_LOOP, ('--> INSIDE == %0.1f, OUTSIDE == %0.1f ==> RGB == (%d,%d,%d) ***' % (g_inside, g_outside, rgb[0], rgb[1], rgb[2])))
    time.sleep(SLEEP_BETWEEN_NEOPIXEL_UPDATES_SEC)

  debug(DEBUG_SIGNAL, 'Exited main thread.')

