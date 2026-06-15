import pyaudio
import numpy as np
import time
from typing import Literal

class AudioDevice:
    def __init__ (self, in_out: Literal["input", "output"], id: int, name: str, channels: int):
        self.in_out = in_out
        self.id = id
        self.name = name
        self.channels = channels
    
    def __str__(self):
        return f"{self.id} - {self.name} ({self.channels} channels)"


class AudioSensor:
    def __init__(self, use_agc=True):
        self.USE_AGC = use_agc 

        self._input_device = 1
        self._output_device = 0
        
        # --- Configuration ---
        self.RATE = 44100
        self.CHUNK = 256
        self.FREQ_MIN = 500
        self.FREQ_MAX = 5000
        
        # AGC Configuration
        self.TARGET_LEVEL = 8000.0
        self.ALPHA = 0.05
        self.MAX_GAIN = 10.0
        self.running_average = 0.0
        
        # Thread-safe variable for the main loop to read
        self.current_display_data = {"amp": 0.0, "gain": " OFF "}
        
        # --- Pre-Computed Math ---
        self.window = np.hanning(self.CHUNK)
        self.WINDOW_CORRECTION = 2.0 
        
        fft_freqs = np.fft.rfftfreq(self.CHUNK, d=1.0/self.RATE)
        self.mask = (fft_freqs >= self.FREQ_MIN) & (fft_freqs <= self.FREQ_MAX)
        
        # --- PyAudio Setup ---
        self.p = pyaudio.PyAudio()
        
        # Dynamically determine the correct number of channels
        try:
            default_device = self.p.get_default_input_device_info()
            self.CHANNELS = int(default_device.get('maxInputChannels', 1))
            # Fallback if device reports 0 channels for some reason
            if self.CHANNELS < 1: self.CHANNELS = 1 
        except IOError:
            print("Error: No default audio input device found.")
            self.CHANNELS = 1
        
        self.stream = None

        self.running = True
        self.halted = False
            
        
    
    def getDevices(self, in_out):
        input = False
        if (in_out == 'input'):
            input = True
        elif (in_out == 'output'):
            input = False
        else:
            return
        which_get = 'maxInputChannels' if input == True else 'maxOutputChannels'
        info = self.p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        devices = []
        for i in range(0, numdevices):
            if (self.p.get_device_info_by_host_api_device_index(0, i).get(which_get)) > 0:
                device_info = self.p.get_device_info_by_host_api_device_index(0, i)
                device = AudioDevice(in_out, i,
                                     device_info.get('name'),
                                     device_info.get('maxInputChannels'))
                devices.append(device)
                print(device)
        return devices
    
    @property
    def input_device(self):
        return self._input_device

    @input_device.setter
    def input_device(self, value):
        self._input_device = value

    @property
    def output_device(self):
        return self._output_device

    @output_device.setter
    def output_device(self, value):
        self._output_device = value

    def _set_input(self, input: int):
        self.input_device = input

    def _process_audio(self, in_data, frame_count, time_info, status):
        # 1. Convert to floats
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        
        # 1b. Fix channel mismatch by converting stereo/multi-channel to mono
        if self.CHANNELS > 1:
            audio_data = audio_data.reshape(-1, self.CHANNELS).mean(axis=1)

        # 2. Apply window and calculate FFT
        windowed_data = audio_data * self.window
        fft_data = np.fft.rfft(windowed_data)

        # 3. Apply mask, normalize, and correct for windowing
        magnitudes = np.abs(fft_data[self.mask]) * (2.0 / self.CHUNK) * self.WINDOW_CORRECTION

        # 4. Calculate raw acoustic energy
        band_amplitude = np.sqrt(np.sum(magnitudes**2)) if len(magnitudes) > 0 else 0.0

        # --- 5. THE TOGGLE LOGIC ---
        if self.USE_AGC:
            if self.running_average == 0.0:
                self.running_average = band_amplitude 
            else:
                self.running_average = (self.ALPHA * band_amplitude) + ((1.0 - self.ALPHA) * self.running_average)

            safe_average = max(self.running_average, 1.0)
            dynamic_gain = min(self.TARGET_LEVEL / safe_average, self.MAX_GAIN)
            normalized_amplitude = band_amplitude * dynamic_gain
            
            gain_display = f"{dynamic_gain:4.1f}x" 
        else:
            normalized_amplitude = band_amplitude
            gain_display = " OFF "

        # Pass data to the main thread instead of printing here
        self.current_display_data = {
            "amp": normalized_amplitude,
            "gain": gain_display
        }

        return (in_data, pyaudio.paContinue)

    def pause(self):
        if self.stream and not self.stream.is_stopped():
            self.stream.stop_stream()

    def resume(self):
        if self.stream and self.stream.is_stopped():
            self.stream.start_stream()

    def start(self):
        mode = "ON" if self.USE_AGC else "OFF"
        print(f"* recording (AGC: {mode}, Channels: {self.CHANNELS}) - Press Ctrl+C to stop")
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=self.input_device,
            output=True,
            output_device_index=self.output_device,
            frames_per_buffer=self.CHUNK,
            stream_callback=self._process_audio 
        )

        try:
            # Main thread handles the UI/Printing
            while self.running:
                # Only update the UI/Math if the stream is currently active
                if self.stream.is_active():
                    data = self.current_display_data
                    meter_length = int(data["amp"] / 150)  
                    bar = '#' * meter_length
                    
                    print(f"\rGain: {data['gain']} | Amp: {data['amp']:8.2f} | {bar:<50}", end="", flush=True)
                    time.sleep(0.05) 
                else:
                    # If paused, just sleep to prevent locking up the CPU
                    time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n* stopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

if __name__ == "__main__":
    visualizer = AudioSensor(use_agc=True) 
    visualizer.getDevices('input')
    visualizer.start()
    # visualizer.cleanup()