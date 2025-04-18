#!/bin/bash
cd /root/planings
git pull origin main
pip3 install -r requirements.txt
sudo systemctl restart telegram-bot
