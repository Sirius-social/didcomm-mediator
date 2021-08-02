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
    - Admin may **turn on** service for any recipient.
      Mediator operates with any recipient that was established **P2P**/**Pairwise** with mediator 
      dynamically. Any recipient may establish connection dynamically via [RFC 0160](https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol)
      and request any service.
    - Admin may **turn off** service for any recipient. Admin may send invitation via email
      with secret link to connection configuration page. 
    - Admin may create/remove static connections via Admin page.  

## 1. Initialize communication with Mediator
TODO

## 2. Grand of endpoint. Recipient keys.
TODO

## 3. Samples
TODO