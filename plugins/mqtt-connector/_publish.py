#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Publish to MQTT topics.
"""

import json
import traceback
from meerschaum.utils.typing import SuccessTuple, Any

def publish(
        self,
        topic: str,
        payload: Any,
        qos: int = 0,
        encode_payload: bool = True,
        debug: bool = False,
        **kwargs: Any
    ) -> SuccessTuple:
    """
    Publish a payload to this connector's MQTT topic.

    Parameters
    ----------
    topic: str
        The MQTT topic onto which to publish the payload.

    payload: Any
        The value to be published onto the topic (must be JSON-serializable).

    qos: int, default 0
        Desired quality of service.

    encode_payload: bool, default True
        If `True`, serialize the payload as JSON before publishing.
        Otherwise attempt to pass the payload directly to `paho`.

    Returns
    -------
    A `SuccessTuple` indicating success.
    """
    if encode_payload:
        try:
            payload = json.dumps(payload)
        except Exception as e:
            return False, f"Failed to encode payload as JSON:\n{traceback.format_exc()}"

    try:
        self.publish_client.connect(self.host, self.port, self.keepalive)
    except Exception as e:
        message = f"Failed to connect to MQTT host:\n{traceback.format_exc()}"
        return False, message

    try:
        message_info = self.publish_client.publish(topic, payload, qos=qos)
    except Exception as e:
        return False, f"Failed to publish message to '{topic}':\n{traceback.format_exc()}"

    mid = message_info.mid
    success = message_info.rc == 0
    msg = (
        f"Received return code {message_info.rc} for message '{mid}' on topic '{topic}'."
        if not success
        else f"Successfully published message '{mid}' on topic '{topic}'."
    )
    return success, msg
