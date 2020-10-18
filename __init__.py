# -*- coding: utf-8 -*-
import fnmatch
import os

from modules import cbpi, app
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

POWER_VALS = [0, 33, 67, 100]


def closest_power(power):
    return min(POWER_VALS, key=lambda x: abs(x - power))


def listGPIO():
    # Lists any GPIO in found in /sys/class/gpio
    app.logger.info("Listing GPIOs for TriplePower...")
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
    app.logger.info("Seting up GPIO for TriplePower...")
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

    gpios = None
    power_phases = None
    state = 0
    power = 100  # 0, 33, 67, 100

    def init(self):
        self.gpios = [self.gpio1, self.gpio2, self.gpio3]
        self.power_phases = {
            0: [],
            33: [self.gpio1],
            67: [self.gpio1, self.gpio2],
            100: self.gpios,
        }
        for gpio in self.gpios:
            setupGPIO(int(gpio), GPIO_OUT)
            self.switch_gpio(gpio, False)

    def on(self, power=100):
        app.logger.info(
            "TriplePower on called with power %s and self.power set to %s." % (str(power), str(self.power))
        )
        self.state = 1
        self.switch_gpios(power)

    def set_power(self, power):
        app.logger.info("TriplePower set power got power: %s" % str(power))
        if power is None:
            power = 0
        new_power = closest_power(power)
        app.logger.info("TriplePower parsed power to: %s" % str(new_power))
        if self.power != new_power:
            active_gpios = self.power_phases[new_power]
            self.api.notify("TriplePower",
                            "Heater's power was set to %s %%, will use %s phases from now on." % (
                                str(new_power), str(len(active_gpios))),
                            type="info",  # maybe use success?
                            timeout=7500
                            )
        self.power = new_power
        if self.state == 1:
            self.switch_gpios(power)
        return self.power

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

    def switch_gpios(self, power):
        if power is None:
            power = self.power
        else:
            power = closest_power(power)
        active_gpios = self.power_phases[power]
        app.logger.info("TriplePower switches on %s phases..." % (str(len(active_gpios))))
        for gpio in self.gpios:
            self.switch_gpio(gpio, (gpio in active_gpios))

    def off(self):
        app.logger.info("TriplePower switches off all three phases...")
        self.switch_gpio(self.gpio1, False)
        self.switch_gpio(self.gpio2, False)
        self.switch_gpio(self.gpio3, False)
        self.state = 0
        self.api.notify("TriplePower",
                        "Heater switched off all three phases.",
                        type="warning",
                        timeout=10000)


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

    @cbpi.try_catch(None)
    def heater_set_power(self, power=100):
        k = self.api.cache.get("kettle").get(self.kettle_id)
        if k.heater is not None:
            self.actor_power(power, int(k.heater))

    def stop(self):
        """
        Invoked when the automatic is stopped.
        Normally you switch off the actors and clean up everything
        :return: None
        """
        super(KettleController, self).stop()
        self.heater_set_power(0)
        self.heater_off()

    def run(self):
        """
        Each controller is exectuted in its own thread. The run method is the entry point
        :return:
        """
        while self.is_running():
            offset = (self.get_target_temp() - self.get_temp())

            should_phase1_be_on = (offset >= float(self.phase_1_on)) and not (offset <= float(self.phase_1_off))
            should_phase2_be_on = (offset >= float(self.phase_2_on)) and not (offset <= float(self.phase_2_off))
            should_phase3_be_on = (offset >= float(self.phase_3_on)) and not (offset <= float(self.phase_3_off))

            num_of_phases = int(should_phase1_be_on) + int(should_phase2_be_on) + int(should_phase3_be_on)
            if num_of_phases == 3:
                self.heater_set_power(100)
                self.heater_on(100)
            elif num_of_phases == 2:
                self.heater_set_power(67)
                self.heater_on(67)
            elif num_of_phases == 1:
                self.heater_set_power(33)
                self.heater_on(33)
            else:
                self.heater_set_power(0)
                self.heater_off()
            self.sleep(1)
