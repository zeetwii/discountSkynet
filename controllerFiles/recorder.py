import pyaudio
import wave
import keyboard
import threading

from openai import OpenAI # needed for calling OpenAI Audio API
import yaml # needed for config
import soundfile as sf # needed to create the audio files

import meshtastic # needed for meshtastic
import meshtastic.serial_interface # needed for physical connection to meshtastic
from pubsub import pub # needed for meshtastic connection

import pygame # needed for audio
pygame.init()

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
OUTPUT_FILE = "recorded_audio.wav"

recording = False  # Flag to control recording
frames = []

# load config settings
with open("./configs/billing.yaml", "r") as ymlfile:
    config = yaml.safe_load(ymlfile)

# load openAI keys into client
client = OpenAI(api_key=config["openai"]["API_KEY"])

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
        # defaults to broadcast, specify a destination ID if you wish
        #interface.sendText("hello mesh")
    print(f"Connected to device")

def onReceive(packet, interface): # called when a packet arrives
        #print(f"Received: {packet}")
        
    print(f"User ID: {packet['from']} \nMessage: {packet['decoded']['text']}")

    text = packet['decoded']['text']

    # generate audio
    response = client.audio.speech.create(model="tts-1", voice="onyx", input=f"{str(text)}",)
    response.stream_to_file("response.mp3")
    #time.sleep(1)

    # plays the response
    channel = pygame.mixer.Sound('response.mp3').play()

    # wait for file to finish playing
    while channel.get_busy():
        pygame.time.wait(100) # wait 100 ms



# set up meshtastic
pub.subscribe(onReceive, "meshtastic.receive.text")
pub.subscribe(onConnection, "meshtastic.connection.established")
interface = meshtastic.serial_interface.SerialInterface()


def record_audio():
    global recording, frames, client
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)
    
    print("Recording started. Press 'r' again to stop.")
    frames = []
    while recording:
        data = stream.read(CHUNK)
        frames.append(data)
    
    print("Recording stopped. Saving file...")
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    with wave.open(OUTPUT_FILE, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    print("File saved as", OUTPUT_FILE)

    # Transcribe the audio using OpenAI API
    with open(OUTPUT_FILE, 'rb') as audio_file:
        response = client.audio.transcriptions.create(model="whisper-1", file=audio_file, response_format="text")

        print("Transcription:", str(response))

        print("Sending over Meshtastic...")
        
        interface.sendText(str(response), destinationId=1927345123)
        print("Message sent!")

def toggle_recording():
    global recording
    if not recording:
        recording = True
        thread = threading.Thread(target=record_audio)
        thread.start()
    else:
        recording = False

print("Press 'r' to start/stop recording.")
keyboard.add_hotkey('r', toggle_recording)
keyboard.wait('esc')  # Press 'esc' to exit the script