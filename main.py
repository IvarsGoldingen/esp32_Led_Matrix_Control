import socket
import time
from tkinter import Tk, Label, Button, StringVar, Entry, Frame
import queue
from queue import Queue
from threading import Timer

from datetime import datetime
from socketToESP import EspSocketCntrl
import logging

log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)


def main_fc():
    main = MainUIClass()


class MainUIClass(Tk):
    """
    UI for controlling LED matrix
    Possible improvements
    TODO: Add more settings like LED brightness, invert screen and others
    TODO: Add more sprites
    """
    MAINLOOP_OTHER_INTERVAL_MS = 200
    # UI constants
    BTN_WIDTH = 25
    # Size of element in a row with 3 elements
    LABEL_ENTRY_SET_SIZE = 18
    # Size of element in a row with 3 elements
    TEXT_ENTRY_SIZE = 122
    # ESP parameters
    HOST = '192.168.94.211'
    PORT = 80
    # Info for UI
    SPRITE_NR_TEXT = "Walker 0 \t" + \
                     "Invader 1 \t" + \
                     "Chevron 2 \t" + \
                     "Heart 3 \t" + \
                     "Arrow1 4 \t" + \
                     "Steamboat 5 \r\n" + \
                     "Fireball 6 \t" + \
                     "Rocket 7 \t" + \
                     "Roll2 8 \t" + \
                     "Pacman2 9 \t" + \
                     "Lines 10 \t" + \
                     "Roll1 11 \r\n" + \
                     "Sailboat 12 \t" + \
                     "Arrow2 13 \t" + \
                     "Wave 14 \t" + \
                     "Pacman 15"

    def __init__(self):
        super().__init__()
        # Queues for sending and receiving data to and from ESP controller
        self.q_in = Queue()
        self.q_out = Queue()
        # Object that conrols the LED matrix using sockets
        self.leds = EspSocketCntrl(host=self.HOST, port=self.PORT, q_main_to_s=self.q_out, q_s_to_main=self.q_in)
        # Start the LED matrix objects. Extends Thread
        self.leds.start()
        # Setup and run IO
        self.set_up_ui()

    def set_up_ui(self):
        self.protocol("WM_DELETE_WINDOW", self.stop_app)
        self.title('LED MATRIX CONTROL')
        self.prepare_ui_elements()
        self.place_ui_elements()
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)
        self.mainloop()

    def mainloop_user(self):
        # Check for status messages
        self.check_esp_q()
        # Start the loop again after delay
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def check_esp_q(self):
        # Check if queue contains status message from controller
        try:
            message = self.q_in.get(block=True, timeout=0)
            logger.debug(f"Main q message {message}")
            if message[:3] == "ST_":
                # Status messages must start with ST_
                self.handle_status_msg(message)
        except queue.Empty:
            # no message in queue
            pass

    def handle_status_msg(self, msg: str):
        # Display received status in UI
        logger.debug("Handling status message")
        try:
            status_code = msg.split("_")[1]
            status_int = int(status_code)
        except Exception as e:
            logger.error(f"Invalid status message {e}")
            return
        self.set_status_in_ui(status_int)

    def set_status_in_ui(self, status: int):
        # Set status label depending on the status controller
        if status == EspSocketCntrl.STATUS_CONNECTED:
            self.lbl_status.config(text="CONNECTED", background="green")
        elif status == EspSocketCntrl.STATUS_DISCONNECTED:
            self.lbl_status.config(text="DISCONNECTED", background="red")
        elif status == EspSocketCntrl.STATUS_SENDING:
            self.lbl_status.config(text="SENDING", background="green")
        elif status == EspSocketCntrl.STATUS_CONNECTING:
            self.lbl_status.config(text="CONNECTING", background="yellow")
        else:
            logger.error(f"Invalid status int {status}")

    def send_msg_to_ESP(self, msg: str):
        # Put message in controller queue
        self.q_out.put(msg)

    def stop_app(self):
        # stop socket connnection to controller
        self.send_msg_to_ESP("QUIT")
        # wait for controller thread to be stopped
        self.leds.join()
        # destroy UI
        self.destroy()

    def start_text_scroll(self):
        # Send message to controller that will start text scroll animation
        speed, sprite_nr, loop_cnt, text = self.gather_ui_settings()
        self.send_msg_to_ESP(f"CS_{speed}_{loop_cnt}")

    def set_text(self):
        # Send message to controller that will set a new text to display, animation will not be started
        speed, sprite_nr, loop_cnt, text = self.gather_ui_settings()
        self.send_msg_to_ESP(f"LT_{text}")

    def start_text_w_sprite(self):
        # Send message to controller that will start text with sprite animation
        speed, sprite_nr, loop_cnt, text = self.gather_ui_settings()
        self.send_msg_to_ESP(f"ST_{speed}_{loop_cnt}_{sprite_nr}")

    def reset_connection(self):
        # disconnect from the controller
        self.send_msg_to_ESP("RESET")

    def gather_ui_settings(self) -> (int, int, int, str):
        # Get settings from UI
        speed = 30
        loop_cnt = 3
        sprite_nr = 99
        set_speed = self.entry_speed_value.get()
        set_sprite_nr = self.entry_sprite_nr_value.get()
        set_text = self.entry_text_value.get()
        set_loop_cnt = self.entry_loop_cnt_value.get()
        try:
            speed = int(set_speed)
            sprite_nr = int(set_sprite_nr)
            loop_cnt = int(set_loop_cnt)
        except Exception as e:
            logger.error(f"Invalid values in UI. {e}")
        return speed, sprite_nr, loop_cnt, set_text

    def prepare_ui_elements(self):
        """
        Create UI elements
        """
        self.lbl_status = Label(self, text='Connecting', width=100)
        self.lbl_sprite_nr_text = Label(self, text=self.SPRITE_NR_TEXT, width=100)
        self.frame_btns = Frame(self)
        self.btn_set_text = Button(self.frame_btns, text='SET TEXT', command=self.set_text, width=self.BTN_WIDTH)
        self.btn_start_text_scroll = Button(self.frame_btns, text='START TEXT SCROLL', command=self.start_text_scroll,
                                            width=self.BTN_WIDTH)
        self.btn_start_text_w_sprite = Button(self.frame_btns, text='START TEXT SPRITE',
                                              command=self.start_text_w_sprite, width=self.BTN_WIDTH)
        self.btn_reset_connection = Button(self.frame_btns, text='RESET CONNECTION', command=self.reset_connection,
                                           width=self.BTN_WIDTH)
        self.entry_text_value = StringVar()
        self.entry_text = Entry(self, width=self.TEXT_ENTRY_SIZE, textvariable=self.entry_text_value, justify='center')
        self.frame_settings = Frame(self)
        self.lbl_speed = Label(self.frame_settings, text="Speed: ", width=self.LABEL_ENTRY_SET_SIZE)
        self.entry_speed_value = StringVar()
        self.entry_speed = Entry(self.frame_settings, width=self.LABEL_ENTRY_SET_SIZE,
                                 textvariable=self.entry_speed_value, justify='center')
        self.lbl_sprite_nr = Label(self.frame_settings, text="Sprite nr.: ", width=self.LABEL_ENTRY_SET_SIZE)
        self.entry_sprite_nr_value = StringVar()
        self.entry_sprite_nr = Entry(self.frame_settings, width=self.LABEL_ENTRY_SET_SIZE,
                                     textvariable=self.entry_sprite_nr_value, justify='center')
        self.lbl_loop_cnt = Label(self.frame_settings, text="Loop count: ", width=self.LABEL_ENTRY_SET_SIZE)
        self.entry_loop_cnt_value = StringVar()
        self.entry_loop_cnt = Entry(self.frame_settings, width=self.LABEL_ENTRY_SET_SIZE,
                                    textvariable=self.entry_loop_cnt_value, justify='center')
        self.entry_text.insert(0, "Hello world!")
        self.entry_speed.insert(0, "30")
        self.entry_sprite_nr.insert(0, "2")
        self.entry_loop_cnt.insert(0, "10")

    def place_ui_elements(self):
        """
        Place created UI elements
        """
        # Settings frame grid
        self.lbl_speed.grid(row=0, column=0)
        self.entry_speed.grid(row=0, column=1)
        self.lbl_loop_cnt.grid(row=0, column=2)
        self.entry_loop_cnt.grid(row=0, column=3)
        self.lbl_sprite_nr.grid(row=0, column=4)
        self.entry_sprite_nr.grid(row=0, column=5)
        # Buttons frame grid
        self.btn_set_text.grid(row=0, column=0)
        self.btn_start_text_scroll.grid(row=0, column=1)
        self.btn_start_text_w_sprite.grid(row=0, column=2)
        self.btn_reset_connection.grid(row=0, column=3)
        # Main grid
        self.lbl_status.grid(row=0, column=0, pady=2)
        self.entry_text.grid(row=1, column=0, pady=2)
        self.frame_btns.grid(row=2, column=0, pady=2)
        self.frame_settings.grid(row=3, column=0, pady=10)
        self.lbl_sprite_nr_text.grid(row=4, column=0, pady=0)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main_fc()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
