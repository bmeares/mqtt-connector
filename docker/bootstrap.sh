#! /bin/bash

mrsm compose up --dry
mrsm compose sync pipes --loop --min-seconds 120
