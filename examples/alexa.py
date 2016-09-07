import json
import os
import platform
import re
import time
from threading import Event, Thread

import pyaudio
import requests

from creds import *

try:
    from respeaker import *
except ImportError:
    import fix_import
    from respeaker import *

# Avoid warning about insure request
# requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

script_dir = os.path.dirname(os.path.realpath(__file__))
response_mp3 = os.path.join(script_dir, 'response.mp3')

token = None


# Get Alexa Token
def gettoken():
    global token
    refresh = refresh_token
    if token:
        return token
    elif refresh:
        payload = {
            "client_id": Client_ID, "client_secret": Client_Secret, "refresh_token": refresh,
            "grant_type": "refresh_token",
        }
        url = "https://api.amazon.com/auth/o2/token"
        r = requests.post(url, data=payload)
        resp = json.loads(r.text)
        token = resp['access_token']
        return token
    else:
        return False


def alexa(audio):
    global response_mp3

    url = 'https://access-alexa-na.amazon.com/v1/avs/speechrecognizer/recognize'
    headers = {'Authorization': 'Bearer %s' % gettoken()}
    # Set parameters to Alexa request for our audio recording
    d = {
        "messageHeader": {
            "deviceContext": [{
                "name": "playbackState",
                "namespace": "AudioPlayer",
                "payload": {
                    "streamId": "",
                    "offsetInMilliseconds": "0",
                    "playerActivity": "IDLE"
                }
            }]
        },
        "messageBody": {
            "profile": "alexa-close-talk",
            "locale": "en-us",
            "format": "audio/L16; rate=16000; channels=1"
        }
    }

    print('Send audio to alexa')
    files = [
        ('file', ('request', json.dumps(d), 'application/json; charset=UTF-8')),
        ('file', ('audio', audio, 'audio/L16; rate=16000; channels=1'))
    ]
    r = requests.post(url, headers=headers, files=files)

    if r.status_code == 200:
        print "Debug: Alexa provided a response"

        for v in r.headers['content-type'].split(";"):
            if re.match('.*boundary.*', v):
                boundary = v.split("=")[1]
        data = r.content.split(boundary)
        for d in data:
            if len(d) >= 1024:
                audio = d.split('\r\n\r\n')[1].rstrip('--')

        # Write response audio to response.mp3 may or may not be played later
        with open(response_mp3, 'wb') as f:
            print('Save response audio to %s' % response_mp3)
            f.write(audio)
            f.close()
            if platform.machine() == 'mips':
                os.system('madplay ' + response_mp3)
            else:
                os.system('mpg123 ' + response_mp3)
    else:
        print "Debug: Alexa threw an error with code: ", r.status_code


mic = None


def task(quit_event):
    global mic

    pixels = PixelRing()
    pixels.set_color(rgb=0x400000)

    pa = pyaudio.PyAudio()
    mic = Microphone(pa)

    pixels.set_color(rgb=0x004000)
    time.sleep(2)
    pixels.off()

    while not quit_event.is_set():
        if mic.wakeup(keyword='alexa'):
            print('wakeup')
            pixels.listen()

            data = mic.listen()
            data = b''.join(data)

            if data:
                pixels.wait()
                alexa(data)

        pixels.off()

    pixels.off()
    mic.close()


def main():
    quit_event = Event()
    thread = Thread(target=task, args=(quit_event,))
    thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('\nquit')
            quit_event.set()
            mic.quit()
            break

    thread.join()


if __name__ == '__main__':
    main()
