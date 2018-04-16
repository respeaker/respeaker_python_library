import logging
import time
import os
import signal
from threading import Thread, Event
from respeaker import Microphone
from respeaker.bing_speech_api import BingSpeechAPI


# get a key from https://www.microsoft.com/cognitive-services/en-us/speech-api
BING_KEY = ''


def task(quit_event):
    mic = Microphone(quit_event=quit_event)
    bing = BingSpeechAPI(key=BING_KEY)

    while not quit_event.is_set():
        if mic.wakeup('respeaker'):
            print('Wake up')
            data = mic.listen()
            try:
                text = bing.recognize(data)
                if text:
                    print('Recognized %s' % text)
                    if 'play music' in text:
                        print('I will play music!')
                        os.system('madplay Tchaikovsky_Concerto_No.1p.mp3')
            except Exception as e:
                print(e.message)


def main():
    logging.basicConfig(level=logging.DEBUG)
    quit_event = Event()

    def signal_handler(sig, frame):
        quit_event.set()
        print('quit')
    signal.signal(signal.SIGINT, signal_handler)

    thread = Thread(target=task, args=(quit_event,))
    thread.daemon = True
    thread.start()
    while not quit_event.is_set():
        time.sleep(1)

    time.sleep(1)


if __name__ == '__main__':
    main()
