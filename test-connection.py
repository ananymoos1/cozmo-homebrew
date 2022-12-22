#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math
from queue import Queue, Empty
import logging
import numpy as np
import cv2 as cv
import pycozmo
import argparse
import threading
import time
import inputs

class InputThread(object):
    """ Thread for reading input. """

    def __init__(self, handler):
        self._stop = False
        self._thread = None
        self._handler = handler

    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self.run, name="InputThread")
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        logging.debug("Input thread stopping...")
        self._stop = True
        self._thread.join()
        logging.debug("Input thread joined.")

    def run(self):
        logging.debug("Input thread started.")
        while not self._stop:
            events = inputs.get_gamepad()
            for event in events:
                self._handler(event)
        logging.debug("Input thread stopped.")


# Set that to False if you want Cozmo's camera to return grayscale images
COLOR_IMG = True

class RCApp(object):
    """ Application class. """

    def __init__(self):
        logging.info("Initializing...")
        self._stop = False
        self.input_thread = InputThread(self._handle_input)
        self.cli = pycozmo.Client()
        self.speed = 0.0        # -1.0 - 1.0
        self.steering = 0.0     # -1.0 - 1.0
        self.speed_left = 0.0   # 0 - 1.0
        self.speed_right = 0.0  # 0 - 1.0
        self.lift = True


# Define the increments for the linear and angular velocities, as well as the
# head angle and lift height
LIN_INC = 20
ANG_INC = math.radians(20)
HEAD_INC = math.radians(2)
LIFT_INC = 5

# This is required since Open CV cannot open displays from threads.
IMG_QUEUE = Queue()

# The linear velocity is expressed in mm/s and the angular velocity in rad/s
LIN_VELOCITY = 0
ANG_VELOCITY = 0
HEAD_TILT = (pycozmo.MAX_HEAD_ANGLE.radians - pycozmo.MIN_HEAD_ANGLE.radians) * 0.1
HEAD_LIGHT = False
LIFT_HEIGHT = pycozmo.MIN_LIFT_HEIGHT.mm

# Those parameters are used to configure the unsharp masking algorithm
# Play with them to get the best image you can
SHARP_AMOUNT = 0.7
SHARP_GAMMA = 2.2






# NOTE: This could be used with cv.filter2D() in place of the unsharp masking
# However, controlling the amount of sharpening is more difficult
# UNSHARP_KERNEL = -1 / 256 * np.array([[1, 4, 6, 4, 1],
#                                       [4, 16, 24, 16, 4],
#                                       [6, 24, -476, 24, 6],
#                                       [4, 16, 24, 16, 4],
#                                       [1, 4, 6, 4, 1]])


def on_camera_img(cli, image):
    """
    A simple function that converts a frame from Cozmo's camera into a BGR
    formatted image to be used by OpenCV.
    :param cli: An instance of the pycozmo.Client class representing the robot.
    :param image: A color/grayscale frame from Cozmo's camera.
    :return: None
    """
    global IMG_QUEUE

    # Convert the image into a numpy array so that OpenCV can manipulate it
    orig_img = np.array(image)

    # Check if we got a color image
    if orig_img.shape[-1] == 3:
        # The thing about OpenCV is that it uses BGR formatted images for
        # reasons
        orig_img = cv.cvtColor(orig_img, cv.COLOR_RGB2BGR)

    # Resize the image
    # The lanczos4 algorithm produces the best results, but might be slow
    # you can use cv.INTER_LINEAR for poorer, but faster results
    resized_img = cv.resize(orig_img, None, fx=2, fy=2,
                            interpolation=cv.INTER_LANCZOS4)

    # Try to reduce the noise using unsharp masking
    # An explanation for this technique can be found here:
    # https://en.wikipedia.org/wiki/Unsharp_masking#Digital_unsharp_masking
    blurred_img = cv.GaussianBlur(resized_img, (3, 3), 0)
    sharp_img = cv.addWeighted(resized_img, 1 + SHARP_AMOUNT, blurred_img,
                               -SHARP_AMOUNT, gamma=SHARP_GAMMA)

    # Send the image back to the main thread for display
    IMG_QUEUE.put(sharp_img)

def stop_all(cli, state):
    """
    This function simply stops all motors and resets the corresponding
    velocities. It is used when Cozmo detects that it has been picked up, or is
    about to fall off a cliff.
    :param cli: An instance of the pycozmo.Client class representing the robot.
    :param state: A boolean set to True if Cozmo has been picked up or is about
    to fall off a cliff. False otherwise.
    :return: None
    """
    global LIN_VELOCITY, ANG_VELOCITY

    # Well as said above, if Cozmo is not touching the ground anymore we stop
    # all motors to prevent any damage
    if state:
        # Stop the motors
        cli.stop_all_motors()

        # Reset the linear and angular velocities
        LIN_VELOCITY = 0
        ANG_VELOCITY = 0

if __name__ == "__main__":
    # Connect to the robot
    with pycozmo.connect() as cli:
        try:
            # Look forward
            cli.set_head_angle(HEAD_TILT)

            # Enable the camera
            cli.enable_camera(enable=True, color=COLOR_IMG)

            # Set the lift in its minimum position
            cli.set_lift_height(height=LIFT_HEIGHT)

            # Handle new incoming images
            cli.add_handler(pycozmo.event.EvtNewRawCameraImage, on_camera_img)

            # Handle cliff and pick-up detection

            # Loop forever
            while True:
                try:
                    # Get the next frame from the camera
                    # A timeout is applied so that the robot might still be
                    # controlled even if no image can be displayed
                    img = IMG_QUEUE.get(timeout=0.2)
                    # Display the frame in a window
                    cv.imshow('Camera', img)
                    IMG_QUEUE.task_done()
                except Empty:
                    logging.warning('Did not get any image from the camera so '
                                    'not displaying any.')

                # Read the next key event
                # /!\ It should be noted that that if OpenCV's window displaying
                # the image received from the camera loses focus, then Cozmo
                # will not answer your commands anymore.
                key = cv.waitKeyEx(1)

                # Act accordingly
                if key == ord('q'):
                    # Exit the program
                    break

                # Losing a bit of computational time to prevent sending motor
                # commands on each loop even when not necessary
                if key in [ord('w'), ord('s'), ord('a'), ord('d')]:
                    if key == ord('w'):
                        print('up')
                        # Increase the linear velocity
                        LIN_VELOCITY = min(pycozmo.MAX_WHEEL_SPEED.mmps,
                                           LIN_VELOCITY + LIN_INC)
                    elif key == ord('s'):
                        # Decrease the linear velocity
                        LIN_VELOCITY = max(-pycozmo.MAX_WHEEL_SPEED.mmps,
                                           LIN_VELOCITY - LIN_INC)
                    elif key == ord('a'):
                        # Increase the angular velocity
                        ANG_VELOCITY = min(pycozmo.MAX_WHEEL_SPEED.mmps / pycozmo.TRACK_WIDTH.mm,
                                           ANG_VELOCITY + ANG_INC)
                    elif key == ord('d'):
                        # Decrease the angular velocity
                        ANG_VELOCITY = max(-pycozmo.MAX_WHEEL_SPEED.mmps / pycozmo.TRACK_WIDTH.mm,
                                           ANG_VELOCITY - ANG_INC)

                    # Compute the velocity of the left and right wheels
                    # using the inverse kinematic equations for a differential
                    # drive robot
                    l_speed = min(pycozmo.MAX_WHEEL_SPEED.mmps,
                                  LIN_VELOCITY - (
                                          pycozmo.TRACK_WIDTH.mm * ANG_VELOCITY) / 2)
                    r_speed = min(pycozmo.MAX_WHEEL_SPEED.mmps,
                                  LIN_VELOCITY + (
                                          pycozmo.TRACK_WIDTH.mm * ANG_VELOCITY) / 2)

                    # Send the command to the robot
                    cli.drive_wheels(lwheel_speed=l_speed,
                                     rwheel_speed=r_speed)

                # Same as above, sacrificing a bit of computational time to
                # prevent sending extraneous head tilt commands
                elif key in [ord('k'), ord('j')]:
                    if key == ord('k'):
                        # Increase head tilt
                        HEAD_TILT = min(pycozmo.MAX_HEAD_ANGLE.radians,
                                        HEAD_TILT + HEAD_INC)
                    elif key == ord('j'):
                        # Decrease head tilt
                        HEAD_TILT = max(pycozmo.MIN_HEAD_ANGLE.radians,
                                        HEAD_TILT - HEAD_INC)

                    # Set the head angle
                    cli.set_head_angle(HEAD_TILT)

                # You get the idea by now
                elif key in [ord('n'), ord('m')]:
                    if key == ord('m'):
                        # Increase the lift height
                        LIFT_HEIGHT = min(pycozmo.MAX_LIFT_HEIGHT.mm,
                                          LIFT_HEIGHT + LIFT_INC)
                    elif key == ord('n'):
                        # Decrease lift height
                        LIFT_HEIGHT = max(pycozmo.MIN_LIFT_HEIGHT.mm,
                                          LIFT_HEIGHT - LIFT_INC)

                    # Set the height of the lift
                    cli.set_lift_height(height=LIFT_HEIGHT)
                elif key == ord('l'):
                    # Toggle the head light
                    HEAD_LIGHT = not HEAD_LIGHT
                    # Set the head light
                    cli.set_head_light(enable=HEAD_LIGHT)

                else:
                    # Other keys have no effect, so skip the rest
                    continue

                print("Velocities: {:.2f} mm/s, {:.2f} deg/s, "
                      "Head angle: {:.2f} deg, "
                      "Head Light enabled: {}".format(LIN_VELOCITY,
                                                      math.degrees(ANG_VELOCITY),
                                                      math.degrees(HEAD_TILT),
                                                      HEAD_LIGHT), end='\r')
        finally:
            # This is to make sure that whatever happens during execution, the
            # robot will always stop driving before exiting
            cli.stop_all_motors()

            # Bring the lift down
            cli.set_lift_height(height=pycozmo.MIN_LIFT_HEIGHT.mm)

            # Set the head down as well
            cli.set_head_angle(pycozmo.MIN_HEAD_ANGLE.radians)

            # Close any display open by OpenCv
            cv.destroyAllWindows()

            # Make sure the queue is empty, even if this has no real impact
            while not IMG_QUEUE.empty():
                IMG_QUEUE.get()
                IMG_QUEUE.task_done()
            IMG_QUEUE.join()
    @staticmethod
    def _get_motor_thrust(r, theta):
        """
        Convert throttle and steering angle to left and right motor thrust.

        https://robotics.stackexchange.com/questions/2011/how-to-calculate-the-right-and-left-speed-for-a-tank-like-rover

        :param r: throttle percentage [0, 100]
        :param theta: steering angle [-180, 180)
        :return: tuple - left motor and right motor thrust percentage [-100, 100]
        """
        # normalize theta to [-180, 180)
        theta = ((theta + 180.0) % 360.0) - 180.0
        # normalize r to [0, 100]
        r = min(max(0.0, r), 100.0)
        v_a = r * (45.0 - theta % 90.0) / 45.0
        v_b = min(100.0, 2.0 * r + v_a, 2.0 * r - v_a)
        if theta < -90.0:
            return -v_b, -v_a
        elif theta < 0:
            return -v_a, v_b
        elif theta < 90.0:
            return v_b, v_a
        else:
            return v_a, -v_b

    def _handle_input(self, e):
        update = False
        update2 = False

        if e.ev_type == "Key":
            # Button event.
            #   e.state = 1 - press
            #   e.state = 0 - release
            if e.code == "BTN_START":
                if e.state == 1:
                    self.stop()
            elif e.code == "BTN_TRIGGER_HAPPY3":
                # XBox 360 Wireless - Up
                if e.state == 1:
                    self._drive_lift(0.8)
                else:
                    self._drive_lift(0.0)
            elif e.code == "BTN_TRIGGER_HAPPY4":
                # XBox 360 Wireless - Down
                if e.state == 1:
                    self._drive_lift(-0.8)
                else:
                    self._drive_lift(0.0)
            elif e.code == "BTN_TRIGGER_HAPPY1":
                # XBox 360 Wireless - Left
                if e.state == 1:
                    self.lift = False
            elif e.code == "BTN_TRIGGER_HAPPY2":
                # XBox 360 Wireless - Right
                if e.state == 1:
                    self.lift = True
            else:
                # Do nothing.
                pass
        elif e.ev_type == "Absolute":
            # Absolute axis event.
            if e.code == "ABS_RX":
                # e.state = -32768 - full left
                # e.state = 32768 - full right
                self.steering = float(-e.state) / 32768.0
                if -0.15 < self.steering < 0.15:
                    self.steering = 0
                update = True
                logging.debug("Steering: {:.02f}".format(self.steering))
            elif e.code == "ABS_Y":
                # e.state = -32768 - full forward
                # e.state = 32768 - full reverse
                self.speed = float(-e.state) / 32768.0
                if -0.15 < self.speed < 0.15:
                    self.speed = 0
                update = True
                logging.debug("Speed: {:.02f}".format(self.speed))
            elif e.code == "ABS_Z":
                # e.state = 0 - 255
                self.speed_left = float(e.state) / 255.0
                update2 = True
                logging.debug("ML: {:.02f}".format(self.speed_left))
            elif e.code == "ABS_RZ":
                # e.state = 0 - 255
                self.speed_right = float(e.state) / 255.0
                update2 = True
                logging.debug("MR: {:.02f}".format(self.speed_right))
            elif e.code == "ABS_HAT0Y":
                if e.state == -1:
                    # Logitech Gamepad F310 - Up
                    self._drive_lift(0.8)
                elif e.state == 1:
                    # Logitech Gamepad F310 - Down
                    self._drive_lift(-0.8)
                else:
                    self._drive_lift(0.0)
            elif e.code == "ABS_HAT0X":
                if e.state == 1:
                    # Logitech Gamepad F310 - Right
                    self.lift = True
                elif e.state == -1:
                    # Logitech Gamepad F310 - Left
                    self.lift = False
                else:
                    pass
            else:
                # Do nothing.
                pass
        else:
            # Do nothing.
            pass

        if update:
            r = self.speed
            theta = -self.steering * 90.0
            if r < 0:
                r *= -1.0
                theta += 180.0
            v_a, v_b = self._get_motor_thrust(r, theta)
            logging.debug("r: {:.02f}; theta: {:.02f}; v_a: {:.02f}; v_b: {:.02f};".format(
                r, theta, v_a, v_b))
            self._drive_wheels(v_a, v_b)

        if update2:
            self._drive_wheels(self.speed_left, self.speed_right)


def parse_args():
    """ Parse command-line arguments. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose')
    args = parser.parse_args()
    return args


def main():
    # Parse command-line.
    args = parse_args()

    # Configure logging.
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(name)-15s %(levelname)-8s %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        level=level)

    #
    for device in inputs.devices:
        print(device)

    # Create application object.
    app = RCApp()
    res = app.init()
    if res:
        app.run()
        app.term()


if __name__ == '__main__':
    main()
