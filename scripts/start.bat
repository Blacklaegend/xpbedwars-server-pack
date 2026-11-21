@echo off
chcp 65001 >nul
title BedWars Server
java -Xms4G -Xmx8G -jar server.jar nogui
pause
