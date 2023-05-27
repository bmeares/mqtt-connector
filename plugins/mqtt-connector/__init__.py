#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Provide the `MQTTConnector`.
"""

__version__ = '0.1.0'

required = ['paho-mqtt']

from meerschaum.connectors import make_connector
from .mqtt_connector import MQTTConnector
