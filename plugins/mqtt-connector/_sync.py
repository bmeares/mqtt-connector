#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Define the `sync()` method for MQTT pipes.
"""

import time
from datetime import datetime, timezone
import meerschaum as mrsm
from meerschaum.utils.typing import Any, List
from meerschaum.utils.formatting import print_tuple
from meerschaum.utils.misc import items_str


def sync(
    self,
    pipe: mrsm.Pipe,
    **kwargs: Any
) -> bool:
    """
    Subscribe to the pipe's topics.
    """
    num_docs = 0

    def _on_message_callback(payload: Any, topic: str = None) -> None:
        """
        Coerce the payload into a sync-able DataFrame.
        """
        nonlocal num_docs
        check_existing = True
        if isinstance(payload, dict):
            doc = payload.copy()
            doc['topic'] = topic
            df = [doc]
        elif isinstance(payload, (int, float, str)):
            dt_col = pipe.columns.get('datetime', 'timestamp')
            doc = {dt_col: datetime.now(timezone.utc), 'value': payload, 'topic': topic}
            df = [doc]
            check_existing = False
        elif isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                for _doc in payload:
                    _doc['topic'] = topic
            df = payload
        else:
            df = payload

        num_docs += len(df)
        kwargs['check_existing'] = check_existing
        sync_success, sync_msg = pipe.sync(df, **kwargs)
        new_msg = f"{pipe}: {sync_msg}"
        print_tuple((sync_success, new_msg))

    topics = self.get_topics_from_pipe(pipe)
    for topic in topics:
        self.subscribe(topic, _on_message_callback, blocking=False)

    return True, f"Syncing {pipe} in a background thread."


@staticmethod
def get_topics_from_pipe(pipe: mrsm.Pipe) -> List[str]:
    """
    Return a list of configured topics for a given pipe.
    """
    _topic = pipe.parameters.get('fetch', {}).get('topic', None)
    _topics = pipe.parameters.get('fetch', {}).get('topics', None)
    if isinstance(_topic, str):
        _topic = [_topic]
    if isinstance(_topics, str):
        _topics = [_topics]

    return (_topic or []) + (_topics or [])
