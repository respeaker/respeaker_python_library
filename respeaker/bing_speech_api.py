"""
 Bing Speech To Text (STT) and Text To Speech (TTS)

 ReSpeaker Python Library
 Copyright (c) 2016 Seeed Technology Limited.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import io
import types
import uuid
import wave

import requests
from monotonic import monotonic


class RequestError(Exception):
    pass


class UnknownValueError(Exception):
    pass


class LocaleError(Exception):
    pass


class BingSpeechAPI:
    def __init__(self, key):
        self.key = key
        self.access_token = None
        self.expire_time = None
        self.locales = {
            "ar-eg": {"Female": "Microsoft Server Speech Text to Speech Voice (ar-EG, Hoda)"},
            "de-DE": {"Female": "Microsoft Server Speech Text to Speech Voice (de-DE, Hedda)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (de-DE, Stefan, Apollo)"},
            "en-AU": {"Female": "Microsoft Server Speech Text to Speech Voice (en-AU, Catherine)"},
            "en-CA": {"Female": "Microsoft Server Speech Text to Speech Voice (en-CA, Linda)"},
            "en-GB": {"Female": "Microsoft Server Speech Text to Speech Voice (en-GB, Susan, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (en-GB, George, Apollo)"},
            "en-IN": {"Male": "Microsoft Server Speech Text to Speech Voice (en-IN, Ravi, Apollo)"},
            "en-US": {"Female": "Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (en-US, BenjaminRUS)"},
            "es-ES": {"Female": "Microsoft Server Speech Text to Speech Voice (es-ES, Laura, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (es-ES, Pablo, Apollo)"},
            "es-MX": {"Male": "Microsoft Server Speech Text to Speech Voice (es-MX, Raul, Apollo)"},
            "fr-CA": {"Female": "Microsoft Server Speech Text to Speech Voice (fr-CA, Caroline)"},
            "fr-FR": {"Female": "Microsoft Server Speech Text to Speech Voice (fr-FR, Julie, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (fr-FR, Paul, Apollo)"},
            "it-IT": {"Male": "Microsoft Server Speech Text to Speech Voice (it-IT, Cosimo, Apollo)"},
            "ja-JP": {"Female": "Microsoft Server Speech Text to Speech Voice (ja-JP, Ayumi, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (ja-JP, Ichiro, Apollo)"},
            "pt-BR": {"Male": "Microsoft Server Speech Text to Speech Voice (pt-BR, Daniel, Apollo)"},
            "ru-RU": {"Female": "Microsoft Server Speech Text to Speech Voice (pt-BR, Daniel, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (ru-RU, Pavel, Apollo)"},
            "zh-CN": {"Female": "Microsoft Server Speech Text to Speech Voice (zh-CN, HuihuiRUS)",
                      "Female2": "Microsoft Server Speech Text to Speech Voice (zh-CN, Yaoyao, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (zh-CN, Kangkang, Apollo)"},
            "zh-HK": {"Female": "Microsoft Server Speech Text to Speech Voice (zh-HK, Tracy, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (zh-HK, Danny, Apollo)"},
            "zh-TW": {"Female": "Microsoft Server Speech Text to Speech Voice (zh-TW, Yating, Apollo)",
                      "Male": "Microsoft Server Speech Text to Speech Voice (zh-TW, Zhiwei, Apollo)"}
        }

        self.session = requests.Session()

    def authenticate(self):
        if self.expire_time is None or monotonic() > self.expire_time:  # first credential request, or the access token from the previous one expired
            # get an access token using OAuth
            credential_url = "https://oxford-speech.cloudapp.net/token/issueToken"
            data = {
                "grant_type": "client_credentials",
                "client_id": "python",
                "client_secret": self.key,
                "scope": "https://speech.platform.bing.com"
            }
            start_time = monotonic()
            response = self.session.post(credential_url, data=data)

            if response.status_code != 200:
                raise RequestError("recognition connection failed")

            credentials = response.json()

            self.access_token, expiry_seconds = credentials["access_token"], float(credentials["expires_in"])

            self.expire_time = start_time + expiry_seconds

    def recognize(self, audio_data, language="en-US", show_all=False):
        self.authenticate()
        if isinstance(audio_data, types.GeneratorType):
            def generate(audio):
                yield self.get_wav_header()
                for a in audio:
                    yield a

            data = generate(audio_data)
        else:
            data = self.to_wav(audio_data)

        params = {
            "version": "3.0",
            "requestid": uuid.uuid4(),
            "appID": "D4D52672-91D7-4C74-8AD8-42B1D98141A5",
            "format": "json",
            "locale": language,
            "device.os": "wp7",
            "scenarios": "ulm",
            "instanceid": uuid.uuid4(),
            "result.profanitymarkup": "0",
        }

        headers = {
            "Authorization": "Bearer {0}".format(self.access_token),
            "Content-Type": "audio/wav; samplerate=16000; sourcerate=16000; trustsourcerate=true",
        }

        url = "https://speech.platform.bing.com/recognize/query"
        response = self.session.post(url, params=params, headers=headers, data=data)

        if response.status_code != 200:
            raise RequestError("recognition connection failed")

        result = response.json()

        if show_all:
            return result
        if "header" not in result or "lexical" not in result["header"]:
            raise UnknownValueError()
        return result["header"]["lexical"]

    def synthesize(self, text, language="en-US", gender="Female"):
        self.authenticate()

        if language not in self.locales.keys():
            raise LocaleError("language locale not supported.")

        lang = self.locales.get(language)

        if gender not in ["Female", "Male", "Female2"]:
            gender = "Female"

        if len(lang) == 1:
            gender = lang.keys()[0]

        service_name = lang[gender]

        body = "<speak version='1.0' xml:lang='en-us'>\
                <voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice>\
                </speak>" % (language, gender, service_name, text)

        headers = {
            "Content-type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "raw-16khz-16bit-mono-pcm",
            "Authorization": "Bearer " + self.access_token,
            "X-Search-AppId": "07D3234E49CE426DAA29772419F436CA",
            "X-Search-ClientID": str(uuid.uuid1()).replace('-', ''),
            "User-Agent": "TTSForPython"
        }

        url = "https://speech.platform.bing.com/synthesize"
        response = self.session.post(url, headers=headers, data=body)
        data = response.content

        return data

    @staticmethod
    def to_wav(raw_data):
        # generate the WAV file contents
        with io.BytesIO() as wav_file:
            wav_writer = wave.open(wav_file, "wb")
            try:  # note that we can't use context manager, since that was only added in Python 3.4
                wav_writer.setframerate(16000)
                wav_writer.setsampwidth(2)
                wav_writer.setnchannels(1)
                wav_writer.writeframes(raw_data)
                wav_data = wav_file.getvalue()
            finally:  # make sure resources are cleaned up
                wav_writer.close()
        return wav_data

    @staticmethod
    def get_wav_header():
        # generate the WAV header
        with io.BytesIO() as f:
            w = wave.open(f, "wb")
            try:
                w.setframerate(16000)
                w.setsampwidth(2)
                w.setnchannels(1)
                w.writeframes('')
                header = f.getvalue()
            finally:
                w.close()
        return header


def main():
    import sys

    # get a key from https://www.microsoft.com/cognitive-services/en-us/speech-api
    BING_KEY = ''

    if len(sys.argv) != 2:
        print('Usage: %s 16k_mono.wav' % sys.argv[0])
        sys.exit(-1)

    wf = wave.open(sys.argv[1])
    if wf.getframerate() != 16000 or wf.getnchannels() != 1 or wf.getsampwidth() != 2:
        print('only support 16000 sample rate, 1 channel and 2 bytes sample width')
        sys.exit(-2)

    # read less than 10 seconds audio data
    n = wf.getnframes()
    if (n / 16000.0) > 10.0:
        n = 16000 * 10

    frames = wf.readframes(n)

    bing = BingSpeechAPI(BING_KEY)

    # recognize speech using Microsoft Bing Voice Recognition
    try:
        text = bing.recognize(frames, language='en-US')
        print('Bing:' + text.encode('utf-8'))
    except RequestError as e:
        print("Could not request results from Microsoft Bing Voice Recognition service; {0}".format(e))


if __name__ == '__main__':
    main()
