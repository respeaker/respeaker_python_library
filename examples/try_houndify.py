#!/usr/bin/env python

import time
from threading import Thread, Event

import pyaudio
import requests

import houndify

try:
    from respeaker import *
except ImportError:
    import fix_import
    from respeaker import *

from creds import *

mic = None
player = None


def get_kickstarter_data():
    KICKSTARTER_URL = "https://www.kickstarter.com/projects/search.json?search=&term=%22respeaker%22"

    r = requests.get(KICKSTARTER_URL)
    data_json = r.json()

    if data_json:
        project = data_json.get('projects')[0]
        backers = project.get("backers_count")
        pledged = project.get("usd_pledged")

        print '%s backers, %s pledged' % (backers, pledged)

        return backers, pledged


def check_kickstarter():
    backers, pledged = get_kickstarter_data()
    print 'we have got %d backers and %s dollars.' % (int(backers), pledged)
    return 'right now, we have got %d backers and raised %s dollars.' % (int(backers), pledged)


def play_music():
    player.play('N23.wav')


def task(quit_event):
    global mic, player

    pixels = PixelRing()
    pixels.set_color(rgb=0x400000)

    bing = BingSpeechAPI(BING_KEY)
    pa = pyaudio.PyAudio()
    mic = Microphone(pa)
    player = Player(pa)

    class MyListener(houndify.HoundListener):
        def __init__(self):
            self.transcript = None
            self.handler = None
            self.spoken_response = ''

        def onPartialTranscript(self, transcript):
            if self.transcript != transcript:
                print transcript
                self.transcript = transcript
                if not self.handler:
                    if transcript.find('how many backers do we have') >= 0 or transcript.find(
                            'how is our campaign going') >= 0 or transcript.find('where are we') >= 0:
                        self.handler = check_kickstarter
                    elif transcript.find('play music') >= 0:
                        self.handler = play_music

        def onFinalResponse(self, response):
            if not self.handler and response["Status"] == 'OK':
                for result in response["AllResults"]:
                    self.spoken_response += result["SpokenResponseLong"]  # result["SpokenResponse"]

                print "response: " + self.spoken_response
                if not self.spoken_response:
                    self.spoken_response = "Sorry, I didn't understand what you said"

        def onTranslatedResponse(self, response):
            print "\nTranslated response: " + response

        def onError(self, err):
            print "ERROR"

    client = houndify.StreamingHoundClient(HOUNDIFY_CLIENT_ID, HOUNDIFY_CLIENT_KEY, "respeaker")
    client.setLocation(22.5431, 114.0579)

    pixels.set_color(rgb=0x004000)
    time.sleep(2)
    pixels.off()

    while not quit_event.is_set():
        if mic.wakeup(keyword='alexa', stop_stream=False):
            print('\nListening')
            pixels.listen()
            data = mic.listen()
            listener = MyListener()
            client.start(listener)
            for d in data:
                client.fill(d)
                if listener.handler:
                    break

            pixels.wait()
            client.finish()
            if listener.handler:
                spoken_text = listener.handler()
            else:
                spoken_text = listener.spoken_response

            pixels.off()  # pixels.speak()
            if spoken_text:
                audio = bing.synthesize(spoken_text)
                player.play_raw(audio)

        pixels.off()

    pixels.off()
    mic.close()


def main():
    global mic

    quit_event = Event()
    thread = Thread(target=task, args=(quit_event,))
    thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('\nQuit')
            quit_event.set()
            mic.quit()
            break

    thread.join()


if __name__ == '__main__':
    main()
