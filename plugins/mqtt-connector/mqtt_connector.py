#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Define the `MQTTConnector`.
"""

import meerschaum as mrsm
from meerschaum.connectors import make_connector, Connector
from meerschaum.utils.typing import Optional, Any, List, Dict
from meerschaum.utils.pool import get_pool


@make_connector
class MQTTConnector(Connector):
    """
    Ingest data from MQTT topics.
    """

    REQUIRED_ATTRIBUTES = ['host']
    DEFAULT_PORT: int = 1883
    DEFAULT_KEEPALIVE: int = 60
    DEFAULT_TRANSPORT: str = 'tcp'
    DEFAULT_CLEAN_SESSION: bool = True

    from ._subscribe import subscribe, _subscribe_on_connect, _on_message, mqtt_topic_to_regex
    from ._publish import publish
    from ._fetch import fetch, get_topics_from_pipe


    @property
    def topics(self) -> Dict[str, int]:
        """
        Return the of currently subscribed topics and their associated quality of service values.
        """
        _topics = self.__dict__.get('_topics', None)
        if _topics is None:
            _topics = {}
            self._topics = _topics
        return _topics


    @property
    def port(self) -> int:
        """
        Return the port for this connector (default `1883`).
        """
        return self.__dict__.get('port', self.DEFAULT_PORT)


    @property
    def clean_session(self) -> bool:
        """
        Return the `clean_session` value for this connector (default `True`).
        """
        return self.__dict__.get('clean_session', self.DEFAULT_CLEAN_SESSION)


    @property
    def transport(self) -> str:
        """
        Return the `transport` value for this connector.
        May be 'tcp' (default) or 'websockets'.
        """
        return self.__dict__.get('transport', self.DEFAULT_TRANSPORT)

    
    @property
    def keepalive(self) -> int:
        """
        Return the `keepalive` value for this connector (default `60`).
        """
        return self.__dict__.get('keepalive', self.DEFAULT_KEEPALIVE)


    @property
    def client(self) -> 'paho.mqtt.client.Client':
        """
        Return a general MQTT Client object.
        """
        _client = self.__dict__.get('_client', None)
        if _client is not None:
            return _client
        self._client = self.build_client()
        return self._client


    @property
    def publish_client(self) -> 'paho.mqtt.client.Client':
        """
        Return the MQTT Client object used internally for publishing only.
        """
        _publish_client = self.__dict__.get('_publish_client', None)
        if _publish_client is not None:
            return _publish_client
        self._publish_client = self.build_client()
        return self._publish_client


    @property
    def subscribe_client(self) -> 'paho.mqtt.client.Client':
        """
        Return the MQTT Client object used internally for subscribing only.
        """
        _subscribe_client = self.__dict__.get('_subscribe_client', None)
        if _subscribe_client is not None:
            return _subscribe_client
        self._subscribe_client = self.build_client()
        return self._subscribe_client


    def build_client(self) -> 'paho.mqtt.client.Client':
        """
        Build a new MQTT Client object.
        """
        username = self.__dict__.get('username', None)
        password = self.__dict__.get('password', None)

        with mrsm.Venv('mqtt-connector'):
            from paho.mqtt.client import Client
            _client = Client(
                clean_session = self.clean_session,
                transport = self.transport,
            )

        if username and password:
            _client.username_pw_set(username=username, password=password)

        return _client


    @property
    def pool(self) -> 'multiprocessing.pool.ThreadPool':
        """
        Return the ThreadPool to use for callbacks.
        """
        _pool = self.__dict__.get('_pool', None)
        if _pool is not None:
            return _pool
        self._pool = get_pool()
        return self._pool


    def __del__(self) -> None:
        """
        Disconnect the client before deletion.
        """
        _clients = [
            self.__dict__.get('_client', None),
            self.__dict__.get('_subscribe_client', None),
            self.__dict__.get('_publish_client', None),
        ]
        for _client in _clients:
            if _client is not None:
                _client.disconnect()
