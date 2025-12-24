#Alex Anderson
#10-1-25
#State Machine/line-following
import socket
#import keyboard 
from time import *
from pynput import keyboard
"""pynput: On Mac OSX, one of the following must be true:
* The process must run as root. OR
* Your application must be white listed under Enable access for assistive devices. Note that this might require that you package your application, since otherwise the entire Python installation must be white listed."""
import sys
import threading
import enum

socketLock = threading.Lock()

# You should fill this in with your states
class States(enum.Enum):
    STRAIGHT = enum.auto()
    TURNRIGHT = enum.auto()
    TURNLEFT = enum.auto()

# Not a thread because this is the main thread which can be important for GUI access
class StateMachine():

    def __init__(self):
        # CONFIGURATION PARAMETERS
        self.IP_ADDRESS = "192.168.1.106" 	# SET THIS TO THE RASPBERRY PI's IP ADDRESS
        self.CONTROLLER_PORT = 5001
        self.TIMEOUT = 10					# If its unable to connect after 10 seconds, give up.  Want this to be a while so robot can init.
        self.STATE = States.STRAIGHT
        self.RUNNING = True
        self.DIST = False
        
        # connect to the motorcontroller
        try:
            with socketLock:
                self.sock = socket.create_connection( (self.IP_ADDRESS, self.CONTROLLER_PORT), self.TIMEOUT)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print("Connected to RP")
        except Exception as e:
            print("ERROR with socket connection", e)
            sys.exit(0)
    
        # Collect events until released
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def main(self):
        # connect to the robot
        """ The i command will initialize the robot.  It enters the create into FULL mode which means it can drive off tables and over steps: be careful!"""
        with socketLock:
            self.sock.sendall("i /dev/ttyUSB0".encode())
            print("Sent command")
            result = self.sock.recv(128)
            result =  self.sock.recv(128)
            print("\n",result)
            if result.decode() != "i /dev/ttyUSB0":
                self.RUNNING = False
        
        sleep(0.2)
        self.sensors = Sensing(self.sock)
        # Start getting data
        self.sensors.start()

        
        while(self.sensors.leftSensor == -1):
            sleep(0.1)
        #print(self.RUNNING)
        # BEGINNING OF THE CONTROL LOOP
        while(self.RUNNING):
            sleep(0.2)
            if self.STATE == States.STRAIGHT:
                print("running", self.sensors.leftSensor, self.sensors.rightSensor)
                if self.sensors.leftSensor > 300 and self.sensors.rightSensor > 1500 and self.sensors.farRightSensor > 2000 and self.sensors.farLeftSensor > 1500:#both are seeing the ground and not a black line
                    with socketLock:
                        self.sock.sendall("a set_leds(False, False, False, False, 0, 255)".encode())  
                        self.sock.recv(128).decode()
                        self.sock.sendall("a set_song(2,  [[36,32],[43,32],[36,64],[40,32],[41,32],[55,64],[36,128]])".encode())
                        self.sock.recv(128).decode()
                        self.sock.sendall("a play_song(2)".encode())
                        self.sock.recv(128).decode()
                        sleep(10)
                        self.sock.sendall("a drive_straight(20)".encode())
                        self.sock.recv(128).decode()
                    print("straight")
                
                elif self.sensors.rightSensor < 2500 or self.sensors.farRightSensor < 2500:#right sensor is seeing a line
                    self.STATE = States.TURNRIGHT
                    
                    with socketLock:
                        self.sock.sendall("a set_leds(False, False, False, False, 255, 255)".encode()) 
                        self.sock.recv(128).decode()
                        self.sock.sendall("a drive_straight(0)".encode())
                        self.sock.recv(128).decode()
                    
                    print("goin right")


                elif self.sensors.leftSensor < 450 or self.sensors.farLeftSensor < 1300:#left sensor is seeing a line    
                    self.STATE = States.TURNLEFT
                    
                    with socketLock:
                        self.sock.sendall("a set_song(2,  [[36,32],[43,32],[36,64],[40,32],[41,32],[55,64],[36,128]])".encode())
                        self.sock.recv(128).decode()
                        self.sock.sendall("a play_song(2)".encode())
                        self.sock.recv(128).decode()
                        sleep(10)
                        self.sock.sendall("a set_leds(False, False, False, False, 255, 255)".encode()) 
                        self.sock.recv(128).decode()
                        self.sock.sendall("a drive_straight(0)".encode())
                        self.sock.recv(128).decode()
                                        
                    print("goin left")

                else:
                    with socketLock:
                        self.sock.sendall("a set_leds(False, False, False, False, 0, 255)".encode() )  
                        self.sock.recv(128).decode()
                        self.sock.sendall("a drive_straight(20)".encode())
                        self.sock.recv(128).decode()

            elif self.STATE == States.TURNRIGHT:
                with socketLock:
                    self.sock.sendall("a set_song(2,  [[36,32],[43,32],[36,64],[40,32],[41,32],[55,64],[36,128]])".encode())
                    self.sock.recv(128).decode()
                    self.sock.sendall("a play_song(2)".encode())
                    self.sock.recv(128).decode()
                    sleep(10)
                    self.sock.sendall("a set_leds(False, False, False, False, 255, 255)".encode())  
                    self.sock.recv(128).decode()
                    self.sock.sendall("a spin_right(30)".encode())
                    self.sock.recv(128).decode()
                self.STATE = States.STRAIGHT

            elif self.STATE == States.TURNLEFT:
                with socketLock:
                    self.sock.sendall("a set_leds(False, False, False, False, 255, 255)".encode())  
                    self.sock.recv(128).decode()
                    self.sock.sendall("a spin_left(30)".encode())
                    self.sock.recv(128).decode()
                self.STATE = States.STRAIGHT
                
                

                
                 


        # END OF CONTROL LOOP
        
        # First stop any other threads talking to the robot
        self.sensors.RUNNING = False
        self.sensors.join()
        
        # Need to disconnect
        """ The c command stops the robot and disconnects.  The stop command will also reset the Create's mode to a battery safe PASSIVE.  It is very important to use this command!"""
        with socketLock:
            self.sock.sendall("c".encode())
            print(self.sock.recv(128))

        with socketLock:
            self.sock.close()
        # If the user didn't request to halt, we should stop listening anyways
        self.listener.stop()

    def on_press(self, key):
        # WARNING: DO NOT attempt to use the socket directly from here
        try:
            print('alphanumeric key {0} pressed'.format(key.char))
            if key.char == 'd':
                self.DIST = True
        except AttributeError:
            print('special key {0} pressed'.format(key))

    def on_release(self, key):
        # WARNING: DO NOT attempt to use the socket directly from here
        print('{0} released'.format(key))
        if key == keyboard.Key.esc or key == keyboard.Key.ctrl:
            # Stop listener
            self.RUNNING = False
            return False

# END OF STATEMACHINE


class Sensing(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)   # MUST call this to make sure we setup the thread correctly
        self.sock = socket
        self.RUNNING = True
        self.leftSensor = -1
        self.rightSensor = -1
        self.farLeftSensor = -1
        self.farRightSensor = -1
    
    def run(self):
        while self.RUNNING:
            sleep(0.1)
            with socketLock:
                self.sock.sendall("a cliff_front_left_signal".encode())
                self.leftSensor = int(self.sock.recv(128).decode())
            with socketLock:
                self.sock.sendall("a cliff_left_signal".encode())
                self.farLeftSensor = int(self.sock.recv(128).decode())
            with socketLock:
                self.sock.sendall("a cliff_right_signal".encode())
                self.farRightSensor = int(self.sock.recv(128).decode())
            with socketLock:
                self.sock.sendall("a cliff_front_right_signal".encode())
                self.rightSensor = int(self.sock.recv(128).decode())

            print("far Left sensing: ", self.farLeftSensor)
            print("far Right sensing: ", self.farRightSensor)
            #print("Left sensing: ", self.leftSensor)
            #print("Right sensing: ", self.rightSensor)

            # This is where I would get a sensor update
            # Store it in this class
            # You can change the polling frequency to optimize performance, don't forget to use socketLock
            with socketLock:
                self.sock.sendall("a battery_charge".encode())
                print("Battery charge: ", self.sock.recv(128).decode())

# END OF SENSING


if __name__ == "__main__":
    sm = StateMachine()
    sm.main()


