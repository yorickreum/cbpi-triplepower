# TriplePower
Plugin for Craftbeerpi 3.0 to control 3-phases-heaters via GPIOs.

This plugin combines functionality from the base plugin ``hysteresis`` and ``GPIOSystem`` from Peter Marinec (https://github.com/chiefwigms/GPIOSystem) to allow the control of a 3-phases heater by hysteresis. 

This includes an actor `TrippleActor` and a controller/logic `TripleHysteresis`. In the actor's configuration the three GPIO pins each controlling one of the phases of the heater can be set. In the controller is configured with offsets from the target value for when the heater should switch on and off each of the phases. The phases are mapped to the power value of Craftbeerpi 3.0 (where 33 % correspond to 1 phase, 67 % correspond 2 phases, 100 % correspond to 3 phases).
