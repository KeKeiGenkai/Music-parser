#!/bin/bash
# Скопируй на сервер в /home/zavet/run-github-runner.sh и сделай chmod +x
# Используется для systemd, если actions-runner внутри проекта

cd /home/zavet/Music_Parser/actions-runner && exec ./run.sh
