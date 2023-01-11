# KNX_ETS

Send and receive messages to and from knx bus via a knx router. The plugin has to be configured with ets. On the web-interface are buttons to enable the programming mode and to generate a knx-prod-xml file. This file can be used with [Kaenx-Creator](https://github.com/OpenKNX/Kaenx-Creator) or [OpenKnxProducer](https://github.com/OpenKNX/OpenKNXproducer) to generate a knx-prod file for ETS.

## Requirements

The knx python module from https://github.com/thelsing/knx/tree/master/examples/knxPython

## Configuration

### plugin.yaml

```yaml
knx_ets:
    class_name: KnxEts
    class_path: plugins.knx_ets
```


#### Attributes

None yet.

### items.yaml

#### knx_dpt

This attribute set the datapoint type used for conversion from Bus format to internal SmartHomeNG format. It is mandatory.
If you don't provide one the item will be ignored.
The DPT has to match the type of the item!

The following datapoint types are supported:

```
|  DPT        |  Data         |  Type    |  Values
| ----------- | ------------- | -------- | ----------------------------------
|  1          |  1 bit        |  bool    |  True or False
|  2          |  2 bit        |  list    |  [0, 0] - [1, 1]
|  3          |  4 bit        |  list    |  [0, 0] - [1, 7]
|  4.002      |  8 bit        |  str     |  1 character (8859_1) e.g. ‘c’
|  5          |  8 bit        |  num     |  0 - 255
|  5.001      |  8 bit        |  num     |  0 - 100
|  6          |  8 bit        |  num     |  -128 - 127
|  7          |  2 byte       |  num     |  0 - 65535
|  8          |  2 byte       |  num     |  -32768 - 32767
|  9          |  2 byte       |  num     |  -671088,64 - 670760,96
|  10         |  3 byte       |  foo     |  datetime.time
|  11         |  3 byte       |  foo     |  datetime.date
|  12         |  4 byte       |  num     |  0 - 4294967295
|  13         |  4 byte       |  num     |  -2147483648 - 2147483647
|  14         |  4 byte       |  num     |  4-Octet Float Value IEEE 754
|  16         |  14 byte      |  str     |  14 characters (ASCII)
|  16.001     |  14 byte      |  str     |  14 characters (8859_1)
|  17         |  8 bit        |  num     |  Scene: 0 - 63
|  17.001     |  8 bit        |  num     |  Scene: 1 - 64
|  20         |  8 bit        |  num     |  HVAC: 0 - 255
|  24         |  var          |  str     |  unlimited string (8859_1)
|  232        |  3 byte       |  list    |  RGB: [0, 0, 0] - [255, 255, 255]
```


If you are missing one, open a bug report or drop me a message in the knx user forum.

#### knx_go
This is the groupobject number of this item. These numbers must start from 1 and must be continous. (There can't be missing numbers before the last one.)

The values of the other attributes are ignored. The attributes only control the default flags of the generated knxprod-xml file.

#### knx_send
Will result in setting the Transmit-flag.

#### knx_status
Similar to knx_send but will send updates even for changes vie KNX if the knx_status GA differs from the destination GA.

#### knx_listen
Will result in setting the Write-flag and Update-flag.

#### knx_init
Will result in setting the Write-flag, Update-flag and ReadOnInit-flag.

#### knx_cache
Will result in setting the Write-flag, Update-flag and ReadOnInit-flag.

#### knx_reply
Will result in setting the Read-flag.

#### knx_poll
Will result in setting the Write-flag and Update-flag.

#### Example

Value of attributes are besides knx_go are ignored.

```yaml
living_room:

    light:
        type: bool
        knx_dpt: 1
        knx_go: 1
        knx_send: 1/1/3
        knx_listen:
          - 1/1/4
          - 1/1/5
        knx_init: 1/1/4

    temperature:
        type: num
        knx_dpt: 9
        knx_go: 2
        knx_send: 1/1/6
        knx_reply: 1/1/6
        ow_addr: 28.BBBBB20000    # see 1-Wire plugin
        ow_sensor: T              # see 1-Wire plugin

    window:
        type: bool
        knx_dpt: 1
        knx_go: 3
        knx_poll: 1/1/9 | 60
```

### logic.yaml

Not supported yet.
