import tkinter as tk
from tkinter import ttk
import threading
from passthrough2 import AudioSensor, AudioDevice

class App(tk.Tk):
    def __init__(self, sensor: AudioSensor):
        super().__init__()

        self.sensor = sensor

        # --- Window Configuration ---
        self.title('My Application')
        self.geometry('400x400')
        self.minsize(300, 200) # Prevents the window from being squeezed too small
        
        # --- Main Layout ---
        # A main frame acts as a container to hold everything and provides consistent padding
        self.main_frame = ttk.Frame(self, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Initialize UI ---
        self.create_widgets()

        self.update_meter()

    def create_widgets(self):
        # 1. Main Container Configuration
        self.main_frame.columnconfigure(0, weight=1) # Controls column
        self.main_frame.columnconfigure(1, weight=0) # Meter column

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
        # Using rowspan=4 to span the listboxes and buttons
        self.amp_meter.grid(row=1, column=1, rowspan=4, padx=(10, 0), sticky="ns")

    def update_meter(self):
        # Read the amplitude from the sensor thread
        amp = self.sensor.current_display_data.get("amp", 0)
        
        # Update progressbar
        self.amp_meter['value'] = amp
        
        # Schedule the next update (33ms = ~30 FPS)
        self.after(10, self.update_meter)

    def set_input_from_list(self, event):
        # Get the currently selected index
        selection = self.device_listbox.curselection()
        if selection:
            index = selection[0]
            selected_val = self.device_listbox.get(index)
            
            # Update the backend
            self.sensor.input_device = int(selected_val.split()[0])
            print(f"Input changed to ID: {self.sensor.input_device}")
    
    def set_output_from_list(self, event):
        # Get the currently selected index
        selection = self.output_device_listbox.curselection()
        if selection:
            index = selection[0]
            selected_val = self.output_device_listbox.get(index)
            
            # Update the backend
            self.sensor.output_device = int(selected_val.split()[0])
            print(f"Output changed to ID: {self.sensor.output_device}")

    # --- Event Handlers (Logic) ---
    def on_submit(self):
        # Get what the user typed and update the label
        sensor_thread = threading.Thread(target=self.sensor.start, daemon=True)
        sensor_thread.start()
        # self.sensor.start()
    def off_submit(self):
        # Get what the user typed and update the label
        self.sensor.pause()
        # self.sensor.start()

if __name__ == "__main__":
    app = App(AudioSensor())
    app.mainloop()
    # app.sensor.cleanup()