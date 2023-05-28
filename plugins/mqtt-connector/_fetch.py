#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Define the `fetch()` method for syncing into pipes.
"""

from datetime import datetime
import meerschaum as mrsm
from meerschaum.utils.typing import Any, List, SuccessTuple
from meerschaum.utils.misc import parse_df_datetimes, df_from_literal
from meerschaum.utils.formatting import print_tuple

def fetch(
        self,
        pipe: mrsm.Pipe,
        **kwargs: Any
    ) -> bool:
    """
    Subscribe to the pipe's topics.
    """

    if 'value' not in pipe.columns:
        pipe.columns['value'] = 'value'

    def _on_message_callback(payload: Any) -> None:
        """
        Coerce the payload into a sync-able DataFrame.
        """
        check_existing = True
        try:
            if isinstance(payload, dict):
                df = [payload]
            elif isinstance(df, (list, float, str)):
                df = df_from_literal(pipe, payload)
                check_existing = False
            else:
                df = payload
        except Exception as e:
            df = None

        if df is None:
            dt_col = pipe.columns.get('datetime', 'timestamp')
            df = [{dt_col: datetime.utcnow(), 'value': payload}]
            check_existing = False

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

