"""PyAudio Example: full-duplex wire between input and output."""

import sys

import pyaudio

RECORD_SECONDS = 5
CHUNK = 1024
RATE = 44100

INPUT = 0
OUTPUT = 1

p = pyaudio.PyAudio()

def getDevices(in_out):
    input = False
    if (in_out == 'input'):
        input = True
    elif (in_out == 'output'):
        input = False
    else:
        return;
    which_get = 'maxInputChannels' if input == True else 'maxOutputChannels'
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get(which_get)) > 0:
            print(f"{'Input' if input == True else 'Output'} Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get('name'))


# stream = p.open(format=p.get_format_from_width(2),
#                 channels=1 if sys.platform == 'darwin' else 2,
#                 rate=RATE,
#                 input=True,
#                 output=True,
#                 frames_per_buffer=CHUNK,
#                 input_device_index=INPUT,
#                 output_device_index=OUTPUT)

# print('* recording')
# for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
#     stream.write(stream.read(CHUNK))
# print('* done')

# stream.close()
getDevices('input')
getDevices('output')

p.terminate()
