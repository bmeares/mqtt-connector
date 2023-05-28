#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Define the `fetch()` method for syncing into pipes.
"""

from datetime import datetime
import meerschaum as mrsm
from meerschaum.utils.typing import Any, List, SuccessTuple
from meerschaum.utils.formatting import print_tuple

def fetch(
        self,
        pipe: mrsm.Pipe,
        **kwargs: Any
    ) -> bool:
    """
    Subscribe to the pipe's topics.
    """

    def _on_message_callback(payload: Any, topic: str = None) -> None:
        """
        Coerce the payload into a sync-able DataFrame.
        """
        check_existing = True
        if isinstance(payload, dict):
            doc = payload.copy()
            doc['topic'] = topic
            df = [doc]
        elif isinstance(payload, (int, float, str)):
            now = datetime.utcnow()
            dt_col = pipe.columns.get('datetime', 'timestamp')
            doc = {dt_col: datetime.utcnow(), 'value': payload, 'topic': topic}
            df = [doc]
            check_existing = False
        else:
            df = payload

        kwargs['check_existing'] = check_existing
        print_tuple(pipe.sync(df, **kwargs))

    topics = self.get_topics_from_pipe(pipe)
    for topic in topics:
        self.subscribe(topic, _on_message_callback)

    return True


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

