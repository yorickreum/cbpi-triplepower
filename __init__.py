# -*- coding: utf-8 -*-
import fnmatch
import os

from modules import cbpi
from modules.core.controller import KettleController
from modules.core.hardware import ActorBase
from modules.core.props import Property

GPIO_PATH = '/sys/class/gpio'
GPIO_MAX = 200
GPIO_MIN = 0
GPIO_HIGH = '1'
GPIO_LOW = '0'
GPIO_IN = 'in'
GPIO_OUT = 'out'


class NotificationAPI(object):
    def notify(self, headline, message, type="success", timeout=5000):
        self.api.notify(headline, message, type, timeout)


def listGPIO():
    # Lists any GPIO in found in /sys/class/gpio
    try:
        arr = []
        for dirname in os.listdir(GPIO_PATH):
            if fnmatch.fnmatch(dirname, 'gpio[0123456789]*'):
                arr.append(dirname[4:])
        if not arr:
            print('No active GPIO found - using default range!')
            arr = list(range(GPIO_MIN, GPIO_MAX))
        return arr
    except:
        print('Error listing GPIO!')
        return []


def setupGPIO(device, value):
    # Sets up GPIO if not defined on system boot (i.e. /etc/rc.local)
    # echo  <gpio#> > /sys/class/gpio/export
    # echo <in/out> > /sys/class/gpio/gpio<#>/direction
    try:
        if not os.path.exists(GPIO_PATH + ('/gpio%d' % device)):
            with open(GPIO_PATH + '/export', 'w') as fp:
                fp.write(str(device))
            with open(GPIO_PATH + ('/gpio%d/direction' % device), 'w') as fp:
                fp.write('out')
    except:
        print(('Error setting up GPIO%d!' % device))


def outputGPIO(device, value):
    # Outputs new GPIO value
    # echo <1/0> > /sys/class/gpio/gpio<#>/value
    try:
        with open(GPIO_PATH + ('/gpio%d/value' % device), 'w') as fp:
            fp.write(value)
    except:
        print(('Error writing to GPIO%d!' % device))


@cbpi.actor
class TriplePower(ActorBase):
    active = Property.Select("Active", options=["High", "Low"],
                             description="Selects if the GPIO is Active High (On = 1, Off = 0) or Low (On = 0, Off = 1)")
    gpio1 = Property.Select("GPIO 1", listGPIO(),
                            description="GPIO to which the actor's heater #1 is connected"
                            )
    gpio2 = Property.Select("GPIO 2", listGPIO(),
                            description="GPIO to which the actor's heater #2 is connected"
                            )
    gpio3 = Property.Select("GPIO 3", listGPIO(),
                            description="GPIO to which the actor's heater #3 is connected"
                            )

    def init(self):
        setupGPIO(int(self.gpio1), GPIO_OUT)
        setupGPIO(int(self.gpio2), GPIO_OUT)
        setupGPIO(int(self.gpio3), GPIO_OUT)
        self.switch_gpio(self.gpio1, False)
        self.switch_gpio(self.gpio2, False)
        self.switch_gpio(self.gpio3, False)

    def on(self, power=100):
        cbpi.app.logger.info("TriplePower on got power: %s" % str(power))
        self.set_power(power)
        # else:
        #     raise ValueError("Power was none of 0, 33, 66, 99 or 100! Switching all heaters off...")

    def set_power(self, power):
        cbpi.app.logger.info("TriplePower set power got power: %s" % str(power))
        if power is 0:
            self.switch_gpio(self.gpio1, False)
            self.switch_gpio(self.gpio2, False)
            self.switch_gpio(self.gpio3, False)
        elif power == 33:
            self.switch_gpio(self.gpio1, True)
            self.switch_gpio(self.gpio2, False)
            self.switch_gpio(self.gpio3, False)
        elif power == 66:
            self.switch_gpio(self.gpio1, True)
            self.switch_gpio(self.gpio2, True)
            self.switch_gpio(self.gpio3, False)
        elif power is None or power == 99 or power == 100:
            self.switch_gpio(self.gpio1, True)
            self.switch_gpio(self.gpio2, True)
            self.switch_gpio(self.gpio3, True)

    def switch_gpio(self, gpio, switchOn=False):
        if switchOn:
            if self.active == "High":
                outputGPIO(int(gpio), GPIO_HIGH)
            else:  # self.active == "Low"
                outputGPIO(int(gpio), GPIO_LOW)
        else:
            if self.active == "High":
                outputGPIO(int(gpio), GPIO_LOW)
            else:  # self.active == "Low"
                outputGPIO(int(gpio), GPIO_HIGH)

    def off(self):
        self.set_power(0)


@cbpi.controller
class TripleHysteresis(KettleController):
    # Custom Properties

    phase_1_on = Property.Number("Offset Phase #1 On", True, 0,
                                 description="Offset below target temp when heater should switch on phase one.")
    phase_1_off = Property.Number("Offset Phase #1 Off", True, 0,
                                  description="Offset below target temp when heater should switch off phase one.")
    phase_2_on = Property.Number("Offset Phase #2 On", True, 0,
                                 description="Offset below target temp when heater should switch on phase two.")
    phase_2_off = Property.Number("Offset Phase #2 Off", True, 0,
                                  description="Offset below target temp when heater should switch off phase two.")
    phase_3_on = Property.Number("Offset Phase #3 On", True, 0,
                                 description="Offset below target temp when heater should switch on phase three.")
    phase_3_off = Property.Number("Offset Phase #3 Off", True, 0,
                                  description="Offset below target temp when heater should switch off phase three.")

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
            offset = (self.get_target_temp() - self.get_temp())

            should_phase1_be_on = (offset > float(self.phase_1_on)) and not (offset < float(self.phase_1_off))
            should_phase2_be_on = (offset > float(self.phase_2_on)) and not (offset < float(self.phase_2_off))
            should_phase3_be_on = (offset > float(self.phase_3_on)) and not (offset < float(self.phase_3_off))

            num_of_phases = int(should_phase1_be_on) + int(should_phase2_be_on) + int(should_phase3_be_on)
            if num_of_phases == 3:
                self.heater_on(100)
            elif num_of_phases == 2:
                self.heater_on(66)
            elif num_of_phases == 1:
                self.heater_on(33)
            else:
                self.heater_off()
            self.sleep(1)
