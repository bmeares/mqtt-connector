#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Custom actions for testing MQTTConnectors.
"""

import time
import random
import meerschaum as mrsm
from meerschaum.plugins import make_action, add_plugin_argument
from meerschaum.utils.typing import SuccessTuple, Any, Union, Optional, List
from meerschaum.utils.warnings import info


@make_action
def mqtt_test(
        topics: Optional[List[str]] = None,
        min_seconds: Union[float, int] = 1,
        loop: bool = False,
        **kwargs: Any
    ) -> SuccessTuple:
    """
    Emit test messages with `mqtt:local`.
    """
    if not topics:
        return False, f"Provide `--topics` for this action."

    conn = mrsm.get_connector('mqtt:local')
    num_messages = 0

    while True:
        for topic in topics:
            num_messages += 1
            value = random.randint(0, 100)
            conn.publish(topic, value)
            info(
                f"Emitted '{value}' to '{topic}'."
            )
        if not loop:
            break
        info(f"Sleep for {min_seconds} seconds...")
        time.sleep(min_seconds)


    return True, f"Emitted {num_messages} messages."
