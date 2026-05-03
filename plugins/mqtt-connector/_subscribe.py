#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Define methods for subscribing to MQTT topics.
"""

import re
import json
import traceback
from meerschaum.utils.typing import SuccessTuple, Callable, Any, Optional, Union, Dict
from meerschaum.utils.warnings import warn
from meerschaum.utils.misc import filter_keywords


def subscribe(
    self,
    topic: str,
    callback: Callable[[Any], Any],
    qos: int = 0,
    blocking: bool = False,
    decode_payload: bool = True,
    force: bool = False,
    debug: bool = False,
    **kwargs: Any
) -> SuccessTuple:
    """
    Subscribe to this connector's MQTT topic and fire a callback when a message is received.

    Parameters
    ----------
    topic: str
        The MQTT topic to subscribe to.

    callback: Callable[[Any], Any]
        A callback function to be fired when a message is received.
        Accepts the payload of the message.

    qos: int, default 0
        Quality of service level for the subscription (defaults to 0).

    blocking: bool, default False
        If `True`, block execution at this method and loop forever to wait for messages.
        Otherwise use a background thread and continue execution.

    decode_payload: bool, default True
        If `True`, decode the message payload bytes as UTF-8-encoded JSON.
        Otherwise pass the raw bytes into the callback.

    force: bool, default False
        Force a reconnect if the client has already subscribed to a topic.

    Returns
    -------
    A `SuccessTuple` indicating success.
    """
    if topic in self.topics and not force:
        if callback not in self.topics[topic]['callbacks']:
            self.topics[topic]['callbacks'].append(callback)
        return True, "Already subscribed."

    self.topics[topic] = {
        'qos': qos,
        'callbacks': [callback],
        'regex': self.mqtt_topic_to_regex(topic),
        'parser_kwargs': {
            'decode_payload': decode_payload,
        },
    }

    with self._subscribe_lock:
        client = self.subscribe_client
        client.on_message = self._on_message
        client.on_connect = self._subscribe_on_connect
        client.on_disconnect = self._subscribe_on_disconnect
        loop_started = self.__dict__.get('_subscribe_loop_started', False)
        if not loop_started:
            try:
                client.connect_async(self.host, self.port, self.keepalive)
            except Exception:
                self._reset_subscribe_state()
                return False, f"Failed to connect to MQTT host:\n{traceback.format_exc()}"
            if not blocking:
                client.loop_start()
                self._subscribe_loop_started = True
        elif not blocking:
            client.subscribe(topic, qos=qos)

    if not loop_started and blocking:
        self.subscribe_client.loop_forever()

    return True, f"Subscribed to '{topic}' with quality-of-service level {qos}."


def _reset_subscribe_state(self) -> None:
    """
    Tear down the subscribe client and clear all subscription state.
    Called after a failed connect so the next attempt gets a clean slate.
    """
    old_client = self.__dict__.pop('_subscribe_client', None)
    if old_client is not None:
        try:
            old_client.loop_stop()
        except Exception:
            pass
        try:
            old_client.disconnect()
        except Exception:
            pass
    self.__dict__['_subscribe_loop_started'] = False
    self._topics = {}
    self._syncing_pipes = set()


def _subscribe_on_connect(
    self,
    client: 'paho.mqtt.client.Client',
    userdata: 'paho.mqtt.client.MQTTMessageInfo',
    flags: Dict[str, int],
    return_code: int,
) -> None:
    """
    Subscribe to all registered topics upon connecting (handles reconnects).
    """
    if return_code > 0:
        warn(
            f"[{self}] Received return code {return_code} from '{self.host}'.",
            stack=False,
        )
        if return_code == 5:
            warn(f"Are the credentials for '{self}' correct?", stack=False)

    for topic, topic_meta in list(self.topics.items()):
        client.subscribe(topic, qos=topic_meta.get('qos', 0))


def _subscribe_on_disconnect(
    self,
    client: 'paho.mqtt.client.Client',
    userdata: 'paho.mqtt.client.MQTTMessageInfo',
    return_code: int,
) -> None:
    """
    Attempt reconnect on unexpected disconnects.
    """
    if return_code == 0:
        return
    warn(
        f"[{self}] Disconnected from '{self.host}' (rc={return_code}); paho will reconnect.",
        stack=False,
    )


def _on_message(
    self,
    client: 'paho.mqtt.client.Client',
    userdata: 'paho.mqtt.client.MQTTMessageInfo',
    message: 'paho.mqtt.client.MQTTMessage',
) -> Any:
    """
    When messages are received, invoke all matching callbacks.
    """
    matched_topics = {
        subscribed_topic: subscribed_topic_meta
        for subscribed_topic, subscribed_topic_meta in self.topics.items()
        if subscribed_topic_meta['regex'].match(message.topic)
    }

    def parse_matched_topic(topic: str):
        topic_meta = matched_topics[topic]
        decode_payload = topic_meta['parser_kwargs']['decode_payload']
        callbacks = topic_meta['callbacks']
        raw = message.payload
        if not raw:
            return

        if decode_payload:
            try:
                decoded = raw.decode('utf-8')
            except UnicodeDecodeError as e:
                warn(f"Failed to decode payload on topic '{message.topic}': {e}", stack=False)
                payload = raw
            else:
                try:
                    payload = json.loads(decoded)
                except json.JSONDecodeError:
                    payload = decoded
        else:
            payload = raw
        for callback in callbacks:
            callback(payload, **filter_keywords(callback, topic=message.topic))

    return self.pool.map(parse_matched_topic, matched_topics.keys())


@staticmethod
def mqtt_topic_to_regex(topic: str) -> re.Pattern:
    """
    Convert an MQTT topic string to a compiled regex pattern.

    MQTT wildcard rules:
    - `+` matches exactly one topic level (no `/`).
    - `#` matches zero or more levels and must be the last segment.
      `sensors/#` matches `sensors`, `sensors/temp`, `sensors/temp/1`, etc.
    """
    if topic == '#':
        return re.compile(r'^.*$')

    parts = topic.split('/')
    regex_parts = []
    for part in parts:
        if part == '#':
            regex_parts.append('#HASH#')
            break
        elif part == '+':
            regex_parts.append('[^/]+')
        else:
            regex_parts.append(re.escape(part))

    if regex_parts and regex_parts[-1] == '#HASH#':
        regex_parts.pop()
        pattern = '/'.join(regex_parts) + r'(/.*)?'
    else:
        pattern = '/'.join(regex_parts)

    return re.compile('^' + pattern + '$')
