#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Provide the `MQTTConnector`.
"""

__version__ = '0.1.1'

required = ['paho-mqtt']

from meerschaum.connectors import make_connector
from meerschaum.plugins import make_action, add_plugin_argument
from .mqtt_connector import MQTTConnector
from .actions import mqtt_test

add_plugin_argument('--topics', nargs='+', help="MQTT topics to publish to (for `mqtt test`)")
