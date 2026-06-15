"""PyAudio Example: full-duplex wire between input and output."""

import sys

import pyaudio

import numpy as np

import matplotlib as plt

RECORD_SECONDS = 5
CHUNK = 1024
RATE = 44100
FREQ_MIN = 500
FREQ_MAX = 5000

# TEST TONE
VOLUME = 0.5
FREQUENCY = 6000.0

INPUT = 0
OUTPUT = 1

TARGET_LEVEL = 8000.0     # The visual amplitude you want standard sounds to hit
ALPHA = 0.05              # Smoothing factor (0.05 = smooth, 0.2 = fast/aggressive)
MAX_GAIN = 10.0           # Safety limit to prevent amplifying dead silence into static

running_average = 0.0

p = pyaudio.PyAudio()

t = np.arange(int(RATE * RECORD_SECONDS)) / RATE
samples = (VOLUME * 32767.0 * np.sin(2 * np.pi * FREQUENCY * t)).astype(np.float32)
stream = p.open(format=p.get_format_from_width(2),
                channels=1 if sys.platform == 'darwin' else 2,
                rate=RATE,
                input=True,
                output=True,
                frames_per_buffer=CHUNK,
                input_device_index=INPUT,
                output_device_index=OUTPUT)

window = np.hanning(CHUNK)

print('* recording')
for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    
    # 1. Read live from the microphone
    data = stream.read(CHUNK, exception_on_overflow=False)

    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)

    # 3. Apply the window function to smooth the edges of the chunk
    windowed_data = audio_data * window

    # 4. Perform the Real Fast Fourier Transform (rfft)
    fft_data = np.fft.rfft(windowed_data)

    # 5. Calculate the frequencies that correspond to the FFT bins
    fft_freqs = np.fft.rfftfreq(CHUNK, d=1.0/RATE)

    # 6. Create a boolean mask to filter only our target frequency range
    mask = (fft_freqs >= FREQ_MIN) & (fft_freqs <= FREQ_MAX)

    # 7. Calculate the magnitude (amplitude) of the complex FFT output
    magnitudes = np.abs(fft_data[mask]) * 2.0 / CHUNK

    # 8. Calculate the overall amplitude for this specific band
    if len(magnitudes) > 0:
        # Square the magnitudes, sum them, and take the square root
        band_amplitude = np.sqrt(np.sum(magnitudes**2))
    else:
        band_amplitude = 0.0

    if running_average == 0.0:
        # Instantly set it on the very first loop to avoid a slow ramp-up
        running_average = band_amplitude 
    else:
        # Smoothly update it using the EMA formula
        running_average = (ALPHA * band_amplitude) + ((1.0 - ALPHA) * running_average)

    # 2. Prevent division by zero if the room is perfectly, digitally silent
    safe_average = max(running_average, 1.0)

    # 3. Calculate how much we need to multiply the audio to hit our target
    dynamic_gain = TARGET_LEVEL / safe_average

    # 4. Clamp the gain so we don't accidentally multiply a quiet room by 500x
    dynamic_gain = min(dynamic_gain, MAX_GAIN)

    # 5. Apply the calculated gain to the current raw amplitude
    normalized_amplitude = band_amplitude * dynamic_gain
        
    # Create a simple visual meter in the console
    # Adjust divisor depending on how loud you want the meter to react
    meter_length = int(normalized_amplitude / 150)  
    bar = '#' * meter_length

    # Print with a carriage return (\r) to overwrite the same line
    print(f"\rAmplitude: {normalized_amplitude:8.2f} | {bar:<50}", end="", flush=True)

print('* done')

stream.close()

p.terminate()
