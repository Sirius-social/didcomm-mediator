# Firebase cloud messaging to enable 24/7 messages delivery

Modern Operating systems on mobile devices optimize battery using.

If a user leaves a device unplugged and stationary for a period of time, 
with the screen off, the device enters Doze mode. In Doze mode, 
the system attempts to conserve battery by restricting apps’ access to network and CPU-intensive services

Restrictions that apply to application in doze mode:

- The system ignores wake locks;
- A network connection is not available;
- The system doesn’t perform WiFi, WiFi RTT, and BLE scans;
- Standard AlarmManager alarms will be rescheduled;
- The system doesn’t allow JobScheduler and WorkManager.

![Doze mode](_static/doze.png?raw=true)

## What does it mean? 
It means in production, operating system will drop any tcp connection 
(http/websockets/etc) soon when user close application.


