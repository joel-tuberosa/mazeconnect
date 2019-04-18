#!/usr/bin/env python3

### TO DO
# - display time stamp at each tracking input
# - reformat the output for data analysis
# - rewrite the controller class for each of the different devices

'''
USAGE
    2ac_server.py [OPTION] [FILE...]

DESCRIPTION
    Receives inputs from 2ac_client.py, allocates the reward position and
    program the stimulus presentation given the defined protocol and 
    control the different components of the device.

OPTIONS
    --help
        Display this message

NOTE
    Compatible with Python 3
'''

import getopt, sys, fileinput, socket, random, subprocess, time
from os import path
from queue import Queue
from threading import Event, Thread

HOST = '127.0.0.1'  # localhost
PORT = 13013        # listen port


class Options(dict):

    def __init__(self, argv):
        
        # set default
        self.set_default()
        
        # handle options with getopt
        try:
            opts, args = getopt.getopt(argv[1:], "", ['help'])
        except (getopt.GetoptError, e):
            sys.stderr.write(str(e) + '\n\n' + __doc__)
            sys.exit(1)

        for o, a in opts:
            if o == '--help':
                sys.stdout.write(__doc__)
                sys.exit(0)

        self.args = args
    
    def set_default(self):
    
        # default parameter value
        pass

class Device(object):
    '''
    Common methods for the Monitor and the Controller classes. Allows 
    context manager implementation.
    '''      
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()
        
    def start(self):
        '''
        Starts the device's thread
        '''
        
        self.t.start()
        
    def end(self):
        '''
        Stops the device's thread
        '''
        
        self.stop.set()
        self.t.join()
    
    def running(self):
        return not self.stop.is_set()
    
    def example_function(self):
        while self.running():
            pass
        
class Monitor(Device):
    '''
    Receives information from Ethovision via 2ac_client.py. 'Event' type
    attributes records the mouse position in the maze and the nose pokes.
    '''
    
    # Flags sent by the client app
    STOP            = b'0'
    MOUSE_IN        = b'1'
    MOUSE_OUT       = b'2'
    LEFT_NOSE_POKE  = b'3'
    RIGHT_NOSE_POKE = b'4'
    
    def __init__(self, client="127.0.0.1", port=13013):
        '''
        Open a connection in a child thread, that will continuously
        listen to signals sent from 2ac_client.py.
        
        client      IPv4 client's address
        port        client's connection port
        '''
        
        # host and port that must be compatible with those defined in the
        # 2ac_client.py
        self.client, self.port = client, port
        
        # mouse is in the trail zone
        self.in_trial_zone = Event()
        
        # nose poke recorded on the left
        self.left_nose_poke = Event()
        
        # nose poke recorded on the right
        self.right_nose_poke = Event()
        
        # stop signal
        self.stop = Event()
        
        # setup the server thread
        self.t = Thread(target=self.open_connection, args=())
        
    def nose_poke_side(self):
        if self.left_nose_poke.is_set() and not self.right_nose_poke.is_set():
            return "left"
        if self.right_nose_poke.is_set() and not self.left_nose_poke.is_set():
            return "right"
        if self.left_nose_poke.is_set() and self.right_nose_poke.is_set():
            return "both"
        else:
            return "none"
    
    def clear_nose_poke(self):
        self.left_nose_poke.clear()
        self.right_nose_poke.clear()

    def wait_for_entrance(self, timeout=None):
        t0 = time.time()
        while not self.in_trial_zone.is_set():
            t = time.time()-t0
            if timeout is not None and t >= timeout: 
                return False
            if self.stop.is_set():
                return False
        return True
        
    def wait_for_leaving(self, timeout=None):
        t0 = time.time()
        while self.in_trial_zone.is_set():
            t = time.time()-t0
            if timeout is not None and t >= timeout: 
                return False
            if self.stop.is_set():
                return False
        return True
            
    def wait_for_nose_poke(self, timeout=None):
        t0 = time.time()
        while not any((self.left_nose_poke.is_set(), 
                       self.right_nose_poke.is_set())):
            t = time.time()-t0
            if timeout is not None and t >= timeout:
                return False
            if self.stop.is_set():
                return False
        return True
    
    def open_connection(self):
        '''
        Create a socket, listen to connection form host and port (class
        attributes)
        '''
        
        # open the connection
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.client, self.port))
            s.listen()
            while self.running():
                conn, addr = s.accept()
                with conn:
                    data = conn.recv(1024)
                    if data == self.STOP:
                        self.stop.set()
                        sys.stderr.write("Received stop signal from"
                                         " {}\n".format(addr))
                    elif data == self.MOUSE_IN:
                        self.in_trial_zone.set()
                    elif data == self.MOUSE_OUT:
                        self.in_trial_zone.clear()
                    elif data == self.LEFT_NOSE_POKE:
                        self.left_nose_poke.set()
                    elif data == self.RIGHT_NOSE_POKE:
                        self.right_nose_poke.set()
                    else:
                        sys.stderr.write('Error: unknown signal received from'
                                         ' {}: {}\n'.format(addr, data))
                        self.stop.set()
                    
                    # echoes back the signal
                    conn.sendall(data)
            sys.stderr.write('Stopping...\n')
            
# for testing purpose            
class Controller(Device):
    '''
    Runs commands, asynchronously, spaced with delays.
    '''
    
    def __init__(self):
        
        # the three channels, for sound, light and reward dispenser,
        # respectively
        self.Q = Queue()
       
        # the threads reading from each of the channels and running the
        # command sequences
        self.t = Thread(target=self.command_input, args=())
        
        # a stop value
        self.stop = Event()
        
    def run(self, args=["echo", "."], offset=.0, rest=.0, condition=None, 
                condition_timeout=None):
        if condition is None:
            condition = Event()
            condition.set()
        self.Q.put((args, offset, rest, condition, condition_timeout))
    
    def command_input(self):
        while self.running():
            if not self.Q.empty():
                args, offset, rest, condition, condition_timeout = self.Q.get()
                condition.wait(condition_timeout)
                time.sleep(offset)
                subprocess.check_call(args)
                time.sleep(rest)

# for testing purpose
class Beep(Controller):
    '''
    Play a beep when run. Windows only.
    '''
    
    def run(self):
        condition = Event()
        condition.set()
        self.Q.put("echo \a")

    def command_input(self):
        while self.running():
            if not self.Q.empty():
                args = self.Q.get()
                subprocess.check_call(args, shell=True)
        
class Trials(object):
    '''
    Yields the trial number and the reward position according to a 
    random algorithm or an input list.
    '''
    
    positions = ("left", "right")
    
    def __init__(self, max_repeat=3, seed=None):
        '''
        Returns an instance of the Trials class. 
            
        max_repeat  the maximum number of time the reward is allocated
                    to the same side (default 3)
        
        seed        random seed (default None)
        '''
    
        # parameter values
        self.max_repeat = max_repeat
        self.seed = seed
        if self.seed is not None: random.seed(self.seed)
        
        # record
        self.buffer = []
        self.i = 0
        self.reward_position = None
        
    def next(self):
        
        # change if lasts self.max_repeat are the same
        if len(set(self.buffer)) == 1:
            self.reward_position = abs(self.reward_position - 1)
        
        # ...or define the reward position randomly
        else:
            self.reward_position = random.randint(0,1)
        
        # append to buffer
        self.buffer.append(self.reward_position)
        self.buffer = self.buffer[-self.max_repeat:]
        
        # increments the trial number
        self.i += 1
        
        # return the trial number and the reward position
        return (self.i, self.positions[self.reward_position])                
                
def main0(argv=sys.argv):
    '''tester function with beep'''
    
    if sys.version_info[0] < 3:
        sys.stderr.write("Version error: must be using Python 3")
        return 1
    
    # read options and remove options strings from argv (avoid option 
    # names and arguments to be handled as file names by
    # fileinput.input().
    options = Options(argv)
    sys.argv[1:] = options.args
    
    with Monitor() as monitor, Beep() as beep:
        
        while monitor.running():
        
            # wait for the mouse entrance
            entrance = monitor.wait_for_entrance() 
            if not monitor.running(): break            
            beep.run()

            # test purpose    
            with open("D:/test7ethovision/OF_test/open_field-test02/slog.txt", "a") as fout:
                fout.write("Received info...\n")

            # wait for the mouse to go out
            monitor.wait_for_leaving()
            
    # return 0 if everything succeeded
    return 0

def main(argv=sys.argv):
    
    if sys.version_info[0] < 3:
        sys.stderr.write("Version error: must be using Python 3")
        return 1
    
    # read options and remove options strings from argv (avoid option 
    # names and arguments to be handled as file names by
    # fileinput.input().
    options = Options(argv)
    sys.argv[1:] = options.args
    
    # create an instance of the protocol
    trials = Trials()

    ### In the future, implement more specific device controllers to 
    ### to simplify the command inputs    
    # create an instance of the monitoring server, open connection to 
    # receive signals from 2ac_client.py, create a Controller class 
    # instance for each control to be run in parallel
    with Monitor() as monitor,                                                \
         Controller() as L_light, Controller() as R_light,                    \
         Controller() as R_dispenser, Controller() as L_dispenser,            \
         Controller() as speaker:
    
        # loop over the trials
        while monitor.running():
            
            # get the trial number and reward position
            i, correct = trials.next()
            incorrect = "right" if correct == "left" else "left"
            
            light = R_light if correct == "left" else L_light
            dispenser = L_dispenser if correct == "left" else R_dispenser
            pitch = "high" if correct == "left" else "low"
            
            # wait for the mouse entrance
            entrance = monitor.wait_for_entrance() 
            if not monitor.running(): break

            # clear the nose poke flags
            monitor.clear_nose_poke()
            
            # start the timer
            t0 = time.time()          

            sys.stdout.write("Starting trial #{:04d}: reward on the {}\n".format(
                             i, correct))        
            
            ### protocol specific --------------------------------------#
            # at the mouse entrance in the trail zone, play 1 second of 
            # white noise
            speaker.run(args=["echo", "#{:04d}: white noise".format(i)], 
                        
                        # prevent the speaker from receiving commands 
                        # from 1 second
                        rest=1)
            
            # ... then light up the LED above the no reward port and a
            # specific tone indicates the reward port.
            time.sleep(1.0)
            light.run(args=["echo", "#{:04d}: light on the {}".format(
                                     i, incorrect)])
            speaker.run(args=["echo", "#{:04d}: {} pitch tone".format(
                                       i, pitch)])
            
            # wait for the mouse nose poke
            nose_poke = monitor.wait_for_nose_poke(timeout=10.0)
            t = (time.time() - t0) if nose_poke else 10.0
            
            # define the trial outcome and dispense a reward in case of a
            # correct answer
            if nose_poke:
                if monitor.nose_poke_side() == correct:
                    outcome = "correct"
                    dispenser.run(["echo", "#{:04d}: Cheerio on the {}".format(
                                   i, correct)])
                else:
                    outcome = "incorrect"
            else:
                outcome = "time out"
            sys.stdout.write("#{:04d}: outcome: {}\n".format(i, outcome) +
                             "#{:04d}: time: {:f}s\n".format(i, t))
            
            # wait for the mouse to go out
            monitor.wait_for_leaving()
            sys.stdout.write("#{:04d}: mouse out... \n".format(i))
            
            # delay the next trial
            if outcome == "correct":
                time.sleep(5)
            else:
                time.sleep(15)
            sys.stdout.write("-- waiting for the next trial.\n")
            
            ###-------------------------------------- protocol specific #
    
    # return 0 if everything succeeded
    return 0    
    
# does not execute main if the script is imported as a module
if __name__ == '__main__': 
    sys.exit(main0())
