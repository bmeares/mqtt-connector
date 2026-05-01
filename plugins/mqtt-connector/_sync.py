#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Define the `sync()` method for MQTT pipes.
"""

import struct
import functools
import meerschaum as mrsm
from meerschaum.utils.typing import Any, List, Dict, Optional, Union
from meerschaum.utils.formatting import print_tuple
from meerschaum.utils.warnings import warn


def sync(
    self,
    pipe: mrsm.Pipe,
    **kwargs: Any
) -> bool:
    """
    Subscribe to the pipe's topics.
    """
    if not hasattr(self, '_syncing_pipes'):
        self._syncing_pipes = set()

    pipe_params = pipe.parameters
    mqtt_params = pipe_params.get('mqtt', {}) or {}
    blocking = mqtt_params.get('blocking', False)
    decode_payload = mqtt_params.get('decode_payload', mqtt_params.get('decode', True))
    payload_parser = mqtt_params.get('payload_parser', None)

    topics = self.get_topics_from_pipe(pipe_params)
    for topic in topics:
        pipe_topic_key = (topic, str(pipe))
        if pipe_topic_key in self._syncing_pipes:
            continue

        num_docs_ref = [0]
        callback = functools.partial(
            _on_message_callback,
            pipe=pipe,
            payload_parser=payload_parser,
            sync_kwargs=kwargs,
            num_docs_ref=num_docs_ref,
        )
        self.subscribe(
            topic,
            callback,
            blocking=blocking,
            decode_payload=decode_payload,
        )
        self._syncing_pipes.add(pipe_topic_key)

    return True, f"Syncing {pipe} in a background thread."


def _on_message_callback(
    payload: Any,
    pipe: mrsm.Pipe,
    payload_parser: Optional[Dict[str, Any]],
    sync_kwargs: Dict[str, Any],
    num_docs_ref: List[int],
    topic: str = None,
) -> None:
    check_existing = True
    if payload_parser and isinstance(payload, bytes):
        df = _parse_binary_payload(payload, payload_parser)
        for doc in df:
            doc['topic'] = topic
    elif isinstance(payload, dict):
        doc = payload.copy()
        doc['topic'] = topic
        df = [doc]
    elif isinstance(payload, (int, float, str)):
        doc = {'value': payload, 'topic': topic}
        df = [doc]
        check_existing = False
    elif isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            for _doc in payload:
                _doc['topic'] = topic
        df = payload
    elif isinstance(payload, bytes):
        if not payload:
            return
        try:
            df = [{'value': payload.decode('utf-8'), 'topic': topic}]
            check_existing = False
        except UnicodeDecodeError:
            warn(
                f"Received binary payload on topic '{topic}' with no parser configured; skipping.",
                stack=False,
            )
            return
    else:
        df = payload

    if not df:
        return

    num_docs_ref[0] += len(df)
    sync_success, sync_msg = pipe.sync(df, **{**sync_kwargs, 'check_existing': check_existing})
    new_msg = f"{pipe} ({num_docs_ref[0]} docs):\n{sync_msg}"
    print_tuple((sync_success, new_msg))


@staticmethod
def get_topics_from_pipe(pipe: Union[mrsm.Pipe, Dict[str, Any]]) -> List[str]:
    """
    Return a list of configured topics for a given pipe.
    """
    pipe_params = pipe.parameters if isinstance(pipe, mrsm.Pipe) else pipe
    fetch_params = pipe_params.get('fetch', {}) or {}
    mqtt_params = pipe_params.get('mqtt', {}) or {}
    fetch_topic = fetch_params.get('topic', None) or []
    fetch_topics = fetch_params.get('topics', None) or []
    mqtt_topic = mqtt_params.get('topic', None) or []
    mqtt_topics = mqtt_params.get('topics', None) or []
    if isinstance(fetch_topic, str):
        fetch_topic = [fetch_topic]
    if isinstance(fetch_topics, str):
        fetch_topics = [fetch_topics]
    if isinstance(mqtt_topic, str):
        mqtt_topic = [mqtt_topic]
    if isinstance(mqtt_topics, str):
        mqtt_topics = [mqtt_topics]

    return fetch_topic + fetch_topics + mqtt_topic + mqtt_topics


def _parse_binary_payload(
    payload: bytes,
    parser: Dict[str, Union[str, List[str]]]
) -> List[Dict[str, Any]]:
    """
    Unpack a binary payload according to a struct-format descriptor.

    Parameters
    ----------
    payload: bytes
        The incoming MQTT message payload.
    
    parser: Dict[str, str]
        The dictionary defining the structure of the payload.

    header_format: str
        A `struct` format string for the fixed header.
        Use `x` to skip bytes (e.g. `'<xQB'` skips 1 byte, reads uint64 + uint8).

    header_fields: list[str]
        Field names for each non-padding value in header_format.

    record_count_field: str, optional
        Name of the header field whose value gives the number of repeating records.
        Omit (or set to null) when there is no variable-length record section.

    record_format: str, optional
        A `struct` format string for each repeating record.

    record_fields: list[str], optional
        Field names for each value in record_format.

    Example pipe parameters
    -----------------------
    mqtt:
      decode: false
      parser:
        header:
            format: "<xQB"           # skip version byte, uint64 ts_ms, uint8 num_targets
            fields: [timestamp_ms, num_targets]
        record:
            count_field: num_targets
            format: "<Bff"           # uint8 target_id, float distance, float speed
            fields: [target_id, distance, speed]
    """
    header_params = parser.get('header', {}) or {}
    record_params = parser.get('record', {}) or {}

    header_format = header_params.get('format', '')
    header_fields = header_params.get('fields', [])
    record_format = record_params.get('format', '')
    record_fields = record_params.get('fields', [])
    record_count_field = record_params.get('count_field', None)

    offset = 0
    header_doc: Dict[str, Any] = {}

    if header_format and header_fields:
        header_size = struct.calcsize(header_format)
        header_values = struct.unpack_from(header_format, payload, offset)
        offset += header_size
        header_doc = dict(zip(header_fields, header_values))

    num_records = int(header_doc.get(record_count_field, 1)) if record_count_field else 1

    if record_format and record_fields:
        record_size = struct.calcsize(record_format)
        docs = []
        for _ in range(num_records):
            record_values = struct.unpack_from(record_format, payload, offset)
            offset += record_size
            docs.append({**header_doc, **dict(zip(record_fields, record_values))})
        return docs

    return [header_doc] if header_doc else []
