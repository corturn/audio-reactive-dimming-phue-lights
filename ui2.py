import tkinter as tk
from tkinter import ttk
import threading
import os
from dotenv import load_dotenv
from phue import Bridge
from passthrough2 import AudioSensor, AudioDevice

class App(tk.Tk):
    def __init__(self, sensor: AudioSensor):
        super().__init__()

        self.sensor = sensor

        # --- Hue Bridge Configuration ---
        load_dotenv()
        self.bridge = Bridge(os.getenv("BRIDGE_IP"))
        self.target_light_id = 9
        self.last_brightness = -1

        self.is_light_on = True

        # --- Window Configuration ---
        self.title('Audio Lighting Passthrough')
        self.geometry('400x400')
        self.minsize(300, 200) 
        
        # --- Main Layout ---
        self.main_frame = ttk.Frame(self, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Initialize UI ---
        self.create_widgets()

        # Start the update loops
        self.update_meter()
        self.update_lights()

    def create_widgets(self):
        self.main_frame.columnconfigure(0, weight=1) 
        self.main_frame.columnconfigure(1, weight=0) 

        # --- Column 0: Controls and Lists ---
        self.greeting_label = ttk.Label(
            self.main_frame, 
            text="Lighting Passthrough", 
            font=('Helvetica', 14)
        )
        self.greeting_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Input Device Listbox
        input_devices = self.sensor.getDevices('input')
        device_strings = [str(d) for d in input_devices] if input_devices else ["No Devices Found"]
        
        self.device_listbox = tk.Listbox(self.main_frame, height=5, width=40, exportselection=False)
        self.device_listbox.grid(row=1, column=0, pady=(0, 15), padx=(0, 10))
        for device in device_strings:
            self.device_listbox.insert(tk.END, device)
        if device_strings:
            self.device_listbox.selection_set(0)
        self.device_listbox.bind("<<ListboxSelect>>", self.set_input_from_list)

        # Output Device Listbox
        output_devices = self.sensor.getDevices('output')
        output_device_strings = [str(d) for d in output_devices] if output_devices else ["No Devices Found"]
        
        self.output_device_listbox = tk.Listbox(self.main_frame, height=5, width=40, exportselection=False)
        self.output_device_listbox.grid(row=2, column=0, pady=(0, 15), padx=(0, 10))
        for device in output_device_strings:
            self.output_device_listbox.insert(tk.END, device)
        if output_device_strings:
            self.output_device_listbox.selection_set(0)
        self.output_device_listbox.bind("<<ListboxSelect>>", self.set_output_from_list)

        # Buttons
        self.action_button = ttk.Button(self.main_frame, text="Start", command=self.on_submit)
        self.action_button.grid(row=3, column=0, pady=(0, 5))
        
        self.off_button = ttk.Button(self.main_frame, text="Stop", command=self.off_submit)
        self.off_button.grid(row=4, column=0)

        # --- Column 1: The Meter ---
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

    def update_meter(self):
        amp = self.sensor.current_display_data.get("amp", 0)
        self.amp_meter['value'] = amp
        # UI updates at ~30 FPS
        self.after(33, self.update_meter)

    def update_lights(self):
        if self.sensor.stream and self.sensor.stream.is_active():
            amp = self.sensor.current_display_data.get("amp", 0)
            
            # Define what amplitude is considered "silence"
            SILENCE_THRESHOLD = 300 

            # --- TURN OFF LOGIC ---
            if amp < SILENCE_THRESHOLD:
                # Only send the OFF command if the light is currently on
                if self.is_light_on:
                    try:
                        # Fast transition time for snappy cutoffs
                        command = {'transitiontime': 0.1, 'on': False}
                        threading.Thread(
                            target=self.bridge.set_light, 
                            args=(self.target_light_id, command), 
                            daemon=True
                        ).start()
                        
                        self.is_light_on = False
                        self.last_brightness = 0 # Reset our brightness tracker
                    except Exception as e:
                        print(f"Hue Error (Off): {e}")

            # --- TURN ON / ADJUST LOGIC ---
            else:
                # Map amplitude to Hue's brightness scale
                brightness = int((amp / 8000.0) * 254)
                # Ensure it never drops below 1 if we are turning it ON
                brightness = max(1, min(254, brightness)) 
                
                # Send command if the light was off, OR if the brightness changed enough
                if not self.is_light_on or abs(brightness - self.last_brightness) > 5:
                    try:
                        command = {'transitiontime': 1, 'bri': brightness, 'on': True}
                        threading.Thread(
                            target=self.bridge.set_light, 
                            args=(self.target_light_id, command), 
                            daemon=True
                        ).start()
                        
                        self.last_brightness = brightness
                        self.is_light_on = True
                    except Exception as e:
                        print(f"Hue Error (On/Dim): {e}")

        # Throttle API calls to ~10 FPS
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
    app = App(AudioSensor())
    app.mainloop()