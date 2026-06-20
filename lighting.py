import os
from dotenv import load_dotenv
from phue import Bridge
from pynput import keyboard

# Load environment variables
load_dotenv()

# Initialize Bridge
b = Bridge(os.getenv("BRIDGE_IP"))

# The ID for "Bedroom2" based on your earlier output
BEDROOM_LIGHT_ID = 9 

def on_press(key):
    try:
        # Check if the key pressed has a character value (like '1' or '2')
        if hasattr(key, 'char') and key.char is not None:
            if key.char == '1':
                print(f"Turning ON light {BEDROOM_LIGHT_ID}...")
                b.set_light(BEDROOM_LIGHT_ID, 'on', True)
            
            elif key.char == '2':
                print(f"Turning OFF light {BEDROOM_LIGHT_ID}...")
                b.set_light(BEDROOM_LIGHT_ID, 'on', False)
                
        # Allow the user to press the 'Esc' key to quit the program
        elif key == keyboard.Key.esc:
            print("Exiting program...")
            return False # Returning False stops the listener

    except Exception as e:
        print(f"An error occurred: {e}")

print("Listening for keystrokes...")
print("Press '1' to turn ON Bedroom2")
print("Press '2' to turn OFF Bedroom2")
print("Press 'Esc' to exit the script.")

# Set up the listener to monitor keystrokes
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()