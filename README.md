# `mqtt-connector` Meerschaum Plugin

The `mqtt-connector` plugin provides the `MQTTConnector`, which allows you to easily connect to MQTT brokers from your code:

- Easy-to-use `publish()` and `subscribe()` methods.
- Map multiple callbacks to topics with a single connector.
- Sync data from MQTT topics into Meerschaum pipes.

See [**Methods**](#methods) below for code examples and [**Getting Started**](#getting-started) to quickly bring up a test environment.

## Installation

Here's how to install this plugin depending on your use-case:

- To install into your current environment:  
  ```bash
  mrsm install plugin mqtt-connector
  ```

- To add to your [Compose](https://meerschaum.io/reference/compose/) project:  
  ```yaml
  plugins:
    - "mqtt-connector"
  ```

- To add as a dependency in your own [Meerschaum plugin](https://meerschaum.io/reference/plugins/writing-plugins/):  
  ```python
  required = ['mqtt-connector@api:mrsm']
  ```

- Or to test things out in a preconfigured environment, clone this repository and following the [Getting Started guide](#getting-started) below:  
  ```bash
  git clone https://github.com/bmeares/mqtt-connector
  cd mqtt-connector
  docker compose up -d
  docker compose exec -it mrsm-compose bash
  mrsm compose python
  ```


## Attributes

The only required attribute for `MQTTConnector` is `host`. Consider `mqtt:local` for example:

```bash
export MRSM_MQTT_LOCAL='{
  "host": "localhost"
}'
```

The following optional attributes are accepted (see [paho-mqtt](https://pypi.org/project/paho-mqtt/) for more information):

- `port`  
  (default `1883`)
- `username`
- `password`
- `keepalive`  
  MQTT [Keep Alive](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc385349238) interval in seconds.
- `transport`  
  `'tcp'` (default) or `websockets` (testing needed)
- `clean_session`

## Methods

The fundamental methods for the `MQTTConnector` are `subscribe()` and `publish()`:

> To test these code examples, run `mrsm compose python` in the container (see [Getting Started](#getting-started) below).

```python
import meerschaum as mrsm
conn = mrsm.get_connector('mqtt:local')

### Topic and callback.
msgs = []
conn.subscribe("foo/#", msgs.append)

import time
time.sleep(1)

### Topic and payload.
conn.publish("foo/bar", {"abc": 123})
time.sleep(1)

print(msgs)
# [{'abc': 123}]
```

You may subscribe to multiple topics with the same connector, mapping different callbacks to each:

```python
import meerschaum as mrsm
conn = mrsm.get_connector('mqtt:local')

foo_msgs, bar_msgs = [], []
conn.subscribe("foo/#", foo_msgs.append)
conn.subscribe("bar/#", bar_msgs.append)

import time
time.sleep(1)

conn.publish("foo/1", "foo!")
conn.publish("bar/2", "bar?")
time.sleep(1)

print(foo_msgs)
# ['foo!']

print(bar_msgs)
# ['bar?']
```

Add the keyword argument `topic` to your callback, and the message topic is passed alongside the payload:

```python
import meerschaum as mrsm
conn = mrsm.get_connector('mqtt:local')

from collections import defaultdict
topics_msgs = defaultdict(lambda: [])

def callback(payload, topic=None):
    topics_msgs[topic].append(payload)

conn.subscribe("foo/#", callback)

import time
time.sleep(1)

conn.publish("foo/bar", 123.45)
time.sleep(1)

print(dict(topics_msgs))
# {'foo/bar': [123.45]}
```

## Syncing into Pipes

The `MQTTConnector` provides a `fetch()` method to sync one or more topics into pipes.

**NOTE:** You must keep the main thread alive to receive messages. This can be done with `--loop` and `--min-seconds`:

```bash
$ mrsm compose up --dry
$ mrsm compose sync pipes -c mqtt:local --loop --min-seconds 240
```

### Parameters

Under `pipe.parameters`, set `fetch:topic` (alias `fetch:topics`) to your MQTT topics, e.g.:

```yaml
sync:
  pipes:
    - connector: "mqtt:local"
      metric: "temperature"
      columns:
        datetime: "timestamp"
        topic: "topic"
      parameters:
        fetch:
          topic:
            - "foo/#/temperature"
            - "bar/#/temperature"
```

If your MQTT stream emits simple values, then your pipe will have the following columns:

- `timestamp`  
  The current UTC timestamp. This will be `pipe.columns['datetime']` if set.

- `value`  
  The message payload.

- `topic`  
  The message topic.

This configuration always inserts (i.e. `--skip-check-existing`) because `timestamp` will always be a new value.

### Dictionary Payloads

If the message payload is a dictionary or a list of dictionaries, the `topic` key will be added to each document, and the documents will be passed into `pipe.sync()`.

If the payload is not a float, integer, string, dictionary, or list, then it will be passed into `pipe.sync()` as-is (but this will likely fail to sync, so be careful).

```python
import meerschaum as mrsm
pipe = mrsm.Pipe(
    'mqtt:local', 'temperature',
    columns = {'datetime': 'timestamp'},
    parameters = {
        'fetch': {
            'topic': 'devices/#',
        },
    },
)
### Starts a subscription thread in the background.
pipe.sync()

import time
time.sleep(1)

conn = mrsm.get_connector('mqtt:local')
doc = {'timestamp': '2023-01-01', 'temperature': 75.1}
conn.publish("devices/1", doc)

import time
time.sleep(2)

df = pipe.get_data()
print(df)
#    timestamp  temperature      topic
# 0 2023-01-01         75.1  devices/1
```

## Getting Started

Build and start the container:

```bash
docker compose up --build -d
```

Jump into a shell and begin emitting messages via the test action:

```bash
docker compose exec -it mrsm-compose bash
mrsm compose mqtt test --topics foo/temperature bar/temperature --loop --debug --min-seconds 3
```

In another terminal, start another shell, register the pipes, and start a syncing loop to subscribe and sync the incoming messages.

```bash
docker compose exec -it mrsm-compose bash
mrsm compose up --dry
mrsm compose sync pipes --loop --min-seconds 120
```