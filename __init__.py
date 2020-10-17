# -*- coding: utf-8 -*-

from modules import cbpi
from modules.core.controller import KettleController
from modules.core.hardware import ActorBase
from modules.core.props import Property

try:
    import RPi.GPIO as GPIO

    GPIO.setmode(GPIO.BCM)
except Exception as e:
    print(e)
    pass


@cbpi.actor
class TriplePower(ActorBase):
    gpio1 = Property.Select(
        "GPIO 1",
        options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
        description="GPIO to which the actor's heater #1 is connected"
    )
    gpio2 = Property.Select(
        "GPIO 2",
        options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
        description="GPIO to which the actor's heater #2 is connected"
    )
    gpio3 = Property.Select(
        "GPIO 3",
        options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
        description="GPIO to which the actor's heater #3 is connected"
    )

    def init(self):
        GPIO.setup(int(self.gpio1), GPIO.OUT)
        GPIO.setup(int(self.gpio2), GPIO.OUT)
        GPIO.setup(int(self.gpio3), GPIO.OUT)
        self.off()

    def on(self, power=0):
        if power == 0:
            self.off()
        elif power == 1:
            GPIO.output(int(self.gpio1), 1)
            GPIO.output(int(self.gpio2), 0)
            GPIO.output(int(self.gpio3), 0)
        elif power == 2:
            GPIO.output(int(self.gpio1), 1)
            GPIO.output(int(self.gpio2), 1)
            GPIO.output(int(self.gpio3), 0)
        elif power == 3:
            GPIO.output(int(self.gpio1), 1)
            GPIO.output(int(self.gpio2), 1)
            GPIO.output(int(self.gpio3), 1)
        else:
            self.off()
            raise ValueError("Power was none of 0, 1, 2 or 3! Switching all heaters off...")

    def off(self):
        GPIO.output(int(self.gpio1), 0)
        GPIO.output(int(self.gpio2), 0)
        GPIO.output(int(self.gpio3), 0)


@cbpi.controller
class TripleHysteresis(KettleController):
    # Custom Properties

    on1 = Property.Number("Offset Level #1 On", True, 0,
                          description="Offset below target temp when heater should switch on #1 (one heater). Should be bigger than Offset Off.")
    on2 = Property.Number("Offset Level #2 On", True, 0,
                          description="Offset below target temp when heater should switched on level #2 (two heaters). Should be bigger than Offsets Off and level #1.")
    on3 = Property.Number("Offset Level #3 On", True, 0,
                          description="Offset below target temp when heater should switched on level #3 (three heaters). Should be bigger than Offset Off and level #2.")
    off = Property.Number("Offset Off", True, 0,
                          description="Offset below target temp when heater should switched off. Should be the smallest value.")

    def stop(self):
        '''
        Invoked when the automatic is stopped.
        Normally you switch off the actors and clean up everything
        :return: None
        '''
        super(KettleController, self).stop()
        self.heater_off()

    def run(self):
        """
        Each controller is exectuted in its own thread. The run method is the entry point
        :return:
        """
        while self.is_running():
            if self.get_temp() < self.get_target_temp() - float(self.on1):
                self.heater_on(1)
            if self.get_temp() < self.get_target_temp() - float(self.on2):
                self.heater_on(2)
            if self.get_temp() < self.get_target_temp() - float(self.on3):
                self.heater_on(3)
            elif self.get_temp() >= self.get_target_temp() - float(self.off):
                self.heater_off()
            self.sleep(1)
