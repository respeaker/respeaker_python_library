
import os
import time
from threading import Thread, Event
from respeaker import Microphone
from respeaker import Player
import pyaudio
import sys



mic = None
quit_event = Event()

def main():
    global mic, quit_event

    pa = pyaudio.PyAudio()
    mic = Microphone(pa)
    player = Player(pa)

    while not quit_event.is_set():
        if mic.detect(keyword='hey respeaker'):
            print('wakeup')
            command = mic.detect(max_phrase_ms=6000, max_wait_ms=4000)
            if command:
                print('recognized: ' + command)
                if command.find('play music') > 0:
                    pass


    mic.close()

if __name__ == '__main__':
    thread = Thread(target=main)
    thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('\nquit')
            quit_event.set()
            mic.interrupt(True, True)
            break

    thread.join()

