# Developer Guide

## INTRO
  Before set up developer environment, you should done next requirement steps:

   1. Enter ```alembic upgrade head``` command to initialize database
   2. Type ```python manage.py create_superuser``` to create admin account

## FAQ
This document describes how to start develop mobile applications that acts as 
Edge Agent in DIDComm decentralized environment with self-service. Details on mediate flow you may find in the [Mediation.md](/docs/Mediation.md) doc.

 - **Q**: Why communication with Mediator is running self-service?
   
   **A**: Decentralized system requires developer to avoid central servers that acts
      as accounts and contexts coordinator. Mobile apps developers is being forced
      to work through servers that provide packets delivery through NAT and firewalls
      into mobile application. [DIDComm spec](https://identity.foundation/didcomm-messaging/spec/#purpose-and-scope)
      advise *intermediaries require little trust, and no terms and conditions apply.*
   
 - **Q**: Is there interoperable protocols or specs?

   **A**: Yes, see [specs here](https://identity.foundation/didcomm-messaging/spec/#roles)

 - **Q**: Does this mediator application communicate with any recipient? Does it support any 
          invitations or recipient filters?
   
   **A**: Depends on application settings. There are some alternatives:
    - Mediator will serve any recipient.
      Mediator operates with anyone recipient that was established **P2P**/**Pairwise** with mediator 
      dynamically. Any recipient may establish connection dynamically via [RFC 0160](https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol)
      and request any service. 
    - Admin create static connections via Admin page.

## 1. Initialize communication with Mediator

Take a look at Two cases. 
  - **Case 1**: Recipient, running on mobile agent, does not have P2P connection to communicate 
    with Mediator application. Recipient agent should establish P2P connection to Mediator:
     - Check [Sample source code](../examples/case1_starting.py)
     - P2P connection establishing is covered by [Aries RFC-160](https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol)
     - Before to start establish P2P Mediator must share P2P [invitation](https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol#0-invitation-to-connect)
       among client-side developers. Mediator admin may get invitation json string via Admin page
       ![P2P invitation](_static/invitation.png?raw=true)
       *Invitation has public internet address of endpoint and cryptographic keys.*
     - Mediator uses Websocket as transport for duplex communication, so recipient agent
       should set ```ws://``` as Endpoint address in ```IndyAgent``` service
         ```
         ...
         "service": [
            {
              "id": "did:peer:JHiaU6HisgxjyRMdPfcGtE;indy",
              "priority": 0,
              "recipientKeys": [
                 "JHiaU6HisgxjyRMdPfcGtE#1"
              ],
              "serviceEndpoint": "ws://",  # or "serviceEndpoint": "didcomm:transport/queue" to pull forwarded messages with pickup protocol 
              "type": "IndyAgent"
            },
         ...
         ```
     - If recipient agent has Firebase cloud messaging **device-id**, then it should declare it in DIDDoc service list
       ```
       ...
        {
          "id": "did:peer:JHiaU6HisgxjyRMdPfcGtE;indy",
          "priority": 1,
          "recipientKeys": [],
          "serviceEndpoint": "firebase-device-id",
          "type": "FCMService"
        }
       ...
       ```
       *For this purpose string* **FCMService**  *reserved as service type:* 
     - On finish step Mediator declare in DIDDoc: 
       - Websocket URL to listen endpoint inbound traffic
         ```
         ...
         {
           "id": "did:peer:QNJ354Uc6MKz7wDjEM9qjZ;indy",
           "priority": 1,
           "recipientKeys": [],
           "serviceEndpoint": "ws://mediator.socialsirius.com:8000/ws?endpoint=e2afc79cc785801e4fff71ca0314bae8cf9959f37d05c7ca722721acc91530ab",
           "type": "MediatorService"
         }
         ...
         ```
       - Http Long polling URL to listen endpoint events
         ```
         ...
         {
           "id": "did:peer:QNJ354Uc6MKz7wDjEM9qjZ;indy",
           "priority": 2,
           "recipientKeys": [],
           "serviceEndpoint": "http://mediator.socialsirius.com:8000/polling?endpoint=e2afc79cc785801e4fff71ca0314bae8cf9959f37d05c7ca722721acc91530ab",
           "type": "MediatorService"
         }
         ...
         ```
     - If recipient have set self endpoint to ```didcomm:transport/queue``` value, then mediator will queue all
      forwarded messages to internal queue, so recipient should retrieve them according [P=pickup](https://github.com/Purik/aries-rfcs/tree/main/features/0212-pickup) protocol.
         
  - **Case 2**: Mediator admin created P2P connection. ![Static connection](_static/create_static_connection.png?raw=true).
    Then recipient should have: **mediator endpoint** and **mediator verkey**.
    See [sample source code for details](../examples/case2_check.py)

         

## 2. Grand of endpoint. Recipient keys.
How endpoint works.
![How endpoint works](_static/endpoint.svg?raw=true).

To make able for **Alice** to send messages to **Bob**, Bob should get unique endpoint from his Mediator.
Mediator will deliver all inbound messages to **Bob** with:

- unique websocket url that declared in Mediator DIDDoc (service type *"MediatorService"*)
- unique long-polling http url that declared in Mediator DIDDoc (service type *"MediatorService"*)
- firebase message delivery if no one of delivery mechanisms described above are not active (no active connections)
  and **device-id** declared in **Bob** DIDDoc

See details:
1. protocol to allocate endpoint [RFC-0211](https://github.com/hyperledger/aries-rfcs/tree/main/features/0211-route-coordination)
2. see [sample code](../examples/case3_endpoint.py) how to receive messages from **Alice**

According to [RFC-0211](https://github.com/hyperledger/aries-rfcs/tree/main/features/0211-route-coordination)
**Bob** may create/remove/update self routing keys, check [sample code here](../examples/case4_routing_keys.py)

## 3. Samples

1. Create P2P connection with Mediator [examples/case1_starting.py](../examples/case1_starting.py)
2. Check P2P connection [examples/case2_check.py](../examples/case2_check.py)
3. Allocate Http endpoint (simplex transport) and receive messages from others [examples/case3_endpoint.py](../examples/case3_endpoint.py)
4. Create/Remove/Update routing keys [examples/case4_routing_keys.py](../examples/case4_routing_keys.py)
5. Android Edge-Agent Demo [Android SDK](https://github.com/Sirius-social/DIDComm-Android-Sample)

## 4. Supported in SDK:
1. [Python SDK](https://github.com/Sirius-social/sirius-sdk-python)
2. [Kotlin SDK](https://github.com/Sirius-social/sirius-sdk-kotlin)
3. [Java SDK](https://github.com/Sirius-social/sirius-sdk-java)
4. [Android SDK](https://github.com/Sirius-social/sirius-sdk-android)
5. [PHP SDK](https://github.com/Sirius-social/sirius-sdk-php)

## 5. Pre-requirements before start to write code
Don't forget to update database models by typing ```alembic upgrade head```
