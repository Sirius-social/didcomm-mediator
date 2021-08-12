# Developer Guide

## INTRO
This document describes how to start develop mobile applications that acts as 
Edge Agent in DIDComm decentralized environment with self-service.

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
  - Case 1: Recipient, running on mobile agent, does not have P2P connection to communicate 
    with Mediator application. Recipient agent should establish P2P connection to Mediator:
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
              "serviceEndpoint": "ws://",
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
## 2. Grand of endpoint. Recipient keys.
TODO

## 3. Samples
TODO