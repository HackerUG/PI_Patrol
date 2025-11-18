#mq_sensor.py
import time
import board
import digitalio # Library for digital GPIO access

# --- Sensor Configuration ---
# The MQ-135 module's Digital Output (DO) pin will be connected here.
MQ135_DO_PIN = board.D21  # This corresponds to RPi GPIO 21 (Physical Pin 40)

# The DO pin is typically LOW when gas is detected and HIGH in clean air.
# We will check for the alert condition (LOW).
GAS_DETECTED_STATE = False 

# --- Alert Message (Combined) ---
# Since we only have one digital trigger, we use a single, comprehensive warning.
DIGITAL_ALERT_MESSAGE = (
    "\n\n🚨 CRITICAL HAZARD! (Fumes/Smoke/Pollution) 🚨"
    f"\n\t*Multiple High Pollutants Potential:* Immediate health effects (eyes, throat, breathing difficulties)."
    f"\n\tVENTILATE and check for source (e.g., strong smoke, fumes, or poor ventilation)."
)
# --------------------------------

# Initialize the digital input pin
try:
    mq135_do = digitalio.DigitalInOut(MQ135_DO_PIN)
    mq135_do.direction = digitalio.Direction.INPUT
    mq135_do.pull = digitalio.Pull.UP # Use a pull-up resistor
except Exception as e:
    print(f"Error initializing GPIO pin: {e}")
    print("Ensure the RPi.GPIO library is installed for this functionality.")
    exit()

print("--- MQ-135 Digital Air Quality Reader ---")
print(f"Reading digital data from RPi GPIO pin D21 (Physical Pin 40)...")
print("Adjust sensitivity using the potentiometer on the MQ-135 module.")

try:
    print("\n*Note: MQ-135 requires a long warm-up (up to 24 hrs) for stable readings.*")
    print("\nPress Ctrl+C to exit.")
    
    is_alerting = False
    
    while True:
        # Read the state of the Digital Output pin
        do_value = mq135_do.value

        # Check if the gas threshold has been crossed (typically LOW = Gas Detected)
        if do_value == GAS_DETECTED_STATE:
            if not is_alerting:
                # Print the multi-line alert only once when triggered
                print(DIGITAL_ALERT_MESSAGE)
                is_alerting = True
            
            print(f"\rStatus: GAS DETECTED (Pin State: {do_value})", end='')
            time.sleep(1) # Wait longer during alert state
        
        else:
            # Clear previous alert message and reset state
            if is_alerting:
                print("\n\n\n", end='\r') # Print extra lines to clear the alert message
                is_alerting = False
            
            print(f"\rStatus: Clean Air (Pin State: {do_value})", end='')
            time.sleep(1)

except KeyboardInterrupt:
    print("\nScript terminated by user.")
except Exception as e:
    print(f"\nAn error occurred during the loop: {e}")
