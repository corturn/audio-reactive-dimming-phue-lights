import tkinter as tk
from tkinter import ttk
import threading
import os
from dotenv import load_dotenv
from phue import Bridge
from passthrough2 import AudioSensor, AudioDevice
from pynput import keyboard

class App(tk.Tk):
    def __init__(self, sensor: AudioSensor):
        super().__init__()

        self.sensor = sensor

        # --- Hue Bridge Configuration ---
        load_dotenv()
        self.bridge = Bridge(os.getenv("BRIDGE_IP"))
        
        # --- Multi-Light Configuration ---
        # You can easily add more lights/keys to this list in the future
        self.lights = [
            {
                "id": 9,
                "trigger": "1",
                "last_brightness": -1,
                "is_on": True,
                "smoothed_brightness": 0.0
            },
            {
                "id": 10,
                "trigger": "2",
                "last_brightness": -1,
                "is_on": True,
                "smoothed_brightness": 0.0
            }
        ]

        # Dynamic dictionary to track the held state of our triggers
        self.key_states = {light["trigger"]: False for light in self.lights}

        # --- Smoothing & Averaging Trackers ---
        self.amp_buffer = []

        # Start a background thread to listen to the keyboard globally
        self.key_listener = keyboard.Listener(
            on_press=self.on_global_key_press, 
            on_release=self.on_global_key_release
        )
        self.key_listener.daemon = True # Closes automatically when you exit the app
        self.key_listener.start()

        # --- Window Configuration ---
        self.title('Audio Lighting Passthrough')
        self.geometry('450x850')
        self.minsize(350, 500) 
        
        # --- Variables for Gates & Smoothing ---
        self.lower_gate_var = tk.DoubleVar(value=300.0)
        self.upper_gate_var = tk.DoubleVar(value=8000.0)
        self.smoothing_var = tk.DoubleVar(value=75.0) 
        
        # --- Variables for Filter ---
        self.use_filter_var = tk.BooleanVar(value=False)
        self.freq_min_var = tk.DoubleVar(value=100.0)
        self.freq_max_var = tk.DoubleVar(value=3000.0)

        # --- Variables for AGC ---
        self.use_agc_var = tk.BooleanVar(value=True)
        self.agc_target_var = tk.DoubleVar(value=8000.0)
        self.agc_max_var = tk.DoubleVar(value=10.0)
        self.agc_alpha_var = tk.DoubleVar(value=5.0) 

        # --- Main Layout ---
        self.main_frame = ttk.Frame(self, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Initialize UI ---
        self.create_widgets()

        # Start the update loops
        self.poll_audio()
        self.update_meter()
        self.update_lights()

    # --- Global Key Listeners ---
    def on_global_key_press(self, key):
        try:
            if hasattr(key, 'char') and key.char in self.key_states:
                self.key_states[key.char] = True
        except Exception:
            pass

    def on_global_key_release(self, key):
        try:
            if hasattr(key, 'char') and key.char in self.key_states:
                self.key_states[key.char] = False
        except Exception:
            pass

    def create_widgets(self):
        self.main_frame.columnconfigure(0, weight=1) 
        self.main_frame.columnconfigure(1, weight=0) 

        self.greeting_label = ttk.Label(
            self.main_frame, 
            text="Lighting Passthrough", 
            font=('Helvetica', 14)
        )
        self.greeting_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        input_devices = self.sensor.getDevices('input')
        device_strings = [str(d) for d in input_devices] if input_devices else ["No Devices Found"]
        
        self.device_listbox = tk.Listbox(self.main_frame, height=5, width=40, exportselection=False)
        self.device_listbox.grid(row=1, column=0, pady=(0, 15), padx=(0, 10))
        for device in device_strings:
            self.device_listbox.insert(tk.END, device)
        if device_strings:
            self.device_listbox.selection_set(0)
        self.device_listbox.bind("<<ListboxSelect>>", self.set_input_from_list)

        output_devices = self.sensor.getDevices('output')
        output_device_strings = [str(d) for d in output_devices] if output_devices else ["No Devices Found"]
        
        self.output_device_listbox = tk.Listbox(self.main_frame, height=5, width=40, exportselection=False)
        self.output_device_listbox.grid(row=2, column=0, pady=(0, 15), padx=(0, 10))
        for device in output_device_strings:
            self.output_device_listbox.insert(tk.END, device)
        if output_device_strings:
            self.output_device_listbox.selection_set(0)
        self.output_device_listbox.bind("<<ListboxSelect>>", self.set_output_from_list)

        self.action_button = ttk.Button(self.main_frame, text="Start", command=self.on_submit)
        self.action_button.grid(row=3, column=0, pady=(0, 5))
        
        self.off_button = ttk.Button(self.main_frame, text="Stop", command=self.off_submit)
        self.off_button.grid(row=4, column=0)

        self.meter_label = ttk.Label(self.main_frame, text="Level")
        self.meter_label.grid(row=0, column=1, padx=(10, 0))
        
        self.amp_meter = ttk.Progressbar(
            self.main_frame, 
            orient=tk.VERTICAL, 
            length=230, 
            mode='determinate',
            maximum=10000
        )
        self.amp_meter.grid(row=1, column=1, rowspan=4, padx=(10, 0), sticky="ns")

        self.filter_frame = ttk.LabelFrame(self.main_frame, text="Frequency Filter", padding="10")
        self.filter_frame.grid(row=5, column=0, columnspan=2, pady=(20, 0), sticky="ew")
        self.filter_frame.columnconfigure(1, weight=1)

        self.filter_toggle = ttk.Checkbutton(
            self.filter_frame, text="Enable Filtering", 
            variable=self.use_filter_var, command=self.on_filter_update
        )
        self.filter_toggle.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(self.filter_frame, text="Min Freq").grid(row=1, column=0, sticky="w")
        self.freq_min_slider = ttk.Scale(
            self.filter_frame, from_=20, to=5000, 
            variable=self.freq_min_var, orient=tk.HORIZONTAL,
            command=self.on_filter_update
        )
        self.freq_min_slider.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 5))

        ttk.Label(self.filter_frame, text="Max Freq").grid(row=2, column=0, sticky="w")
        self.freq_max_slider = ttk.Scale(
            self.filter_frame, from_=100, to=15000, 
            variable=self.freq_max_var, orient=tk.HORIZONTAL,
            command=self.on_filter_update
        )
        self.freq_max_slider.grid(row=2, column=1, sticky="ew", padx=(10, 0))

        self.sliders_frame = ttk.LabelFrame(self.main_frame, text="Amplitude Gates", padding="10")
        self.sliders_frame.grid(row=6, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        self.sliders_frame.columnconfigure(1, weight=1)

        ttk.Label(self.sliders_frame, text="Lower Gate (Off)").grid(row=0, column=0, sticky="w")
        self.lower_slider = ttk.Scale(
            self.sliders_frame, from_=0, to=5000, 
            variable=self.lower_gate_var, orient=tk.HORIZONTAL
        )
        self.lower_slider.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 10))

        ttk.Label(self.sliders_frame, text="Upper Gate (Max)").grid(row=1, column=0, sticky="w")
        self.upper_slider = ttk.Scale(
            self.sliders_frame, from_=1000, to=15000, 
            variable=self.upper_gate_var, orient=tk.HORIZONTAL
        )
        self.upper_slider.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 10))

        ttk.Label(self.sliders_frame, text="Smoothing (%)").grid(row=2, column=0, sticky="w")
        self.smooth_slider = ttk.Scale(
            self.sliders_frame, from_=0, to=99, 
            variable=self.smoothing_var, orient=tk.HORIZONTAL
        )
        self.smooth_slider.grid(row=2, column=1, sticky="ew", padx=(10, 0))

        self.agc_frame = ttk.LabelFrame(self.main_frame, text="Auto Gain Control (AGC)", padding="10")
        self.agc_frame.grid(row=7, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        self.agc_frame.columnconfigure(1, weight=1)

        self.agc_toggle = ttk.Checkbutton(
            self.agc_frame, text="Enable AGC", 
            variable=self.use_agc_var, command=self.on_agc_update
        )
        self.agc_toggle.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(self.agc_frame, text="Target Level").grid(row=1, column=0, sticky="w")
        self.agc_target_slider = ttk.Scale(
            self.agc_frame, from_=1000, to=15000, 
            variable=self.agc_target_var, orient=tk.HORIZONTAL,
            command=self.on_agc_update
        )
        self.agc_target_slider.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 5))

        ttk.Label(self.agc_frame, text="Max Gain (x)").grid(row=2, column=0, sticky="w")
        self.agc_max_slider = ttk.Scale(
            self.agc_frame, from_=1.0, to=50.0, 
            variable=self.agc_max_var, orient=tk.HORIZONTAL,
            command=self.on_agc_update
        )
        self.agc_max_slider.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=(0, 5))
        
        ttk.Label(self.agc_frame, text="Response (%)").grid(row=3, column=0, sticky="w")
        self.agc_alpha_slider = ttk.Scale(
            self.agc_frame, from_=0.1, to=100.0, 
            variable=self.agc_alpha_var, orient=tk.HORIZONTAL,
            command=self.on_agc_update
        )
        self.agc_alpha_slider.grid(row=3, column=1, sticky="ew", padx=(10, 0))

    def on_filter_update(self, *args):
        use_filter = self.use_filter_var.get()
        f_min = int(self.freq_min_var.get())
        f_max = max(int(self.freq_max_var.get()), f_min + 1)
        self.sensor.set_filter(use_filter, f_min, f_max)
        
    def on_agc_update(self, *args):
        use_agc = self.use_agc_var.get()
        target = self.agc_target_var.get()
        max_gain = self.agc_max_var.get()
        alpha = self.agc_alpha_var.get() / 100.0 
        self.sensor.set_agc(use_agc, target, max_gain, alpha)

    def poll_audio(self):
        if self.sensor.is_playing():
            # Constantly buffer the raw audio data
            amp = self.sensor.current_display_data.get("amp", 0)
            self.amp_buffer.append(amp)
        self.after(10, self.poll_audio)

    def update_meter(self):
        # Visually kill the meter if NO triggers are pressed, show it if ANY are pressed
        if any(self.key_states.values()):
            amp = self.sensor.current_display_data.get("amp", 0)
        else:
            amp = 0
            
        self.amp_meter['value'] = amp
        self.amp_meter['maximum'] = max(10000, self.upper_gate_var.get() + 2000)
        self.after(33, self.update_meter)

    def update_lights(self):
        if self.sensor.is_playing():
            
            # 1. Calculate the raw audio amplitude once per frame
            if self.amp_buffer:
                raw_amp = sum(self.amp_buffer) / len(self.amp_buffer)
                self.amp_buffer.clear() 
            else:
                raw_amp = self.sensor.current_display_data.get("amp", 0)

            lower_gate = self.lower_gate_var.get()
            upper_gate = max(self.upper_gate_var.get(), lower_gate + 1)
            alpha = max(0.01, 1.0 - (self.smoothing_var.get() / 100.0))

            # 2. Iterate through each light and apply math independently
            for light in self.lights:
                
                # If this specific light's key is pressed, give it the audio. Otherwise, silence.
                if self.key_states.get(light["trigger"], False):
                    amp = raw_amp
                else:
                    amp = 0

                # --- TURN OFF LOGIC ---
                if amp < lower_gate:
                    if light["is_on"]:
                        try:
                            command = {'transitiontime': 4, 'on': False}
                            threading.Thread(
                                target=self.bridge.set_light, 
                                args=(light["id"], command), 
                                daemon=True
                            ).start()
                            light["is_on"] = False
                            light["last_brightness"] = 0 
                            light["smoothed_brightness"] = 0.0 
                        except Exception as e:
                            print(f"Hue Error (Off): {e}")

                # --- TURN ON / ADJUST LOGIC ---
                else:
                    if amp >= upper_gate:
                        target_brightness = 254
                    else:
                        ratio = (amp - lower_gate) / (upper_gate - lower_gate)
                        target_brightness = int(1 + ratio * 253)

                    light["smoothed_brightness"] = (alpha * target_brightness) + ((1.0 - alpha) * light["smoothed_brightness"])
                    
                    brightness = int(light["smoothed_brightness"])
                    brightness = max(1, min(254, brightness)) 
                    
                    if not light["is_on"] or abs(brightness - light["last_brightness"]) > 2:
                        try:
                            command = {'transitiontime': 2, 'bri': brightness, 'on': True}
                            threading.Thread(
                                target=self.bridge.set_light, 
                                args=(light["id"], command), 
                                daemon=True
                            ).start()
                            light["last_brightness"] = brightness
                            light["is_on"] = True
                        except Exception as e:
                            print(f"Hue Error (On/Dim): {e}")

        self.after(100, self.update_lights)

    def set_input_from_list(self, event):
        selection = self.device_listbox.curselection()
        if selection:
            index = selection[0]
            selected_val = self.device_listbox.get(index)
            self.sensor.input_device = int(selected_val.split()[0])
            print(f"Input changed to ID: {self.sensor.input_device}")
    
    def set_output_from_list(self, event):
        selection = self.output_device_listbox.curselection()
        if selection:
            index = selection[0]
            selected_val = self.output_device_listbox.get(index)
            self.sensor.output_device = int(selected_val.split()[0])
            print(f"Output changed to ID: {self.sensor.output_device}")

    def on_submit(self):
        if not hasattr(self, 'sensor_thread') or not self.sensor_thread.is_alive():
            self.sensor_thread = threading.Thread(target=self.sensor.start, daemon=True)
            self.sensor_thread.start()
        else:
            self.sensor.resume()
            
    def off_submit(self):
        self.sensor.pause()

if __name__ == "__main__":
    app = App(AudioSensor(use_filter=False))
    app.mainloop()