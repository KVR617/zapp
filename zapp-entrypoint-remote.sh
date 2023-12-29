#!/usr/bin/env sh

printenv
exec python run.py --junit "$@"
