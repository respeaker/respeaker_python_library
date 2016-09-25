`ReSpeaker <http://respeaker.io>`_ is an open project to create voice enabled objects.
ReSpeaker python library is an open source python library to provide basic functions of voice interaction.

It uses `PocketSphinx <https://github.com/cmusphinx/pocketsphinx>`_ for keyword spotting
and uses `webrtcvad <https://github.com/wiseman/py-webrtcvad>`_ for voice activity detecting.


* Getting started

    import time
    from threading import Thread, Event

    import fix_import
    from respeaker import Microphone


    def task(quit_event):
        mic = Microphone(quit_event=quit_event)

        while not quit_event.is_set():
            if mic.wakeup('respeaker'):
                print('Wake up')
                data = mic.listen()
                text = mic.recognize(data)
                if text:
                    print('Recognized %s' % text)


    def main():
        quit_event = Event()
        thread = Thread(target=task, args=(quit_event,))
        thread.start()
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print('Quit')
                quit_event.set()
                break
        thread.join()

    if __name__ == '__main__':
        main()
