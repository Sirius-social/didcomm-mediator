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

## Firebase delivery Step-By-Step logic

![Doze mode](_static/firebase.svg?raw=true)

1. **Mediator** serve endpoints of **Client Agent**
2. **Client Agent** and **Agent X** has established P2P and communicate with DIDComm messages
3. **Client Agent** running on mobile device and listen inbound traffic via websocket 
   or http long polling
4. Mobile OS suspend **Client Agent** application according battery saving plan, 
  so any tcp sockets will be suspended too.
5. **Agent X** send DIDComm message to endpoint (http url reachable from internet)
6. **Mediator** detect all **Client Agent** tcp connections are unreachable.
7. **Mediator** detect **Client Agent** declared Firebase device-id in DIDDoc
8. **Mediator** wrap inbound envelop DIDComm message to firebase message and send to **Client Agent**
9. **Firebase** put message to Queue in the Google cloud to resume dest application.
10. Mobile OS resume **Client Agent** application cause of non-empty Firebase messages queue

## How to start working with Firebase
- Register your application in [Firebase console](https://cloud.google.com/firestore/docs/client/get-firebase)
- Add support for your Agent application for [iOS](https://firebase.google.com/docs/ios/setup) 
  and [Android](https://firebase.google.com/docs/android/setup)
- Set **server api key** and **sender id** via [environment vars](./AdminGuide.md#environment-variables)
  or via Admin page  

![Configure Firebase with Admin](_static/fcm_admin.png?raw=true)
*configuring firebase secrets with Admin page*