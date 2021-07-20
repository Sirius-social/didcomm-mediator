# Server-side implementation of DID communication (DIDComm).

## Summary
The dominant paradigm in mobile and web development today is duplex request-response. 
You call an API with certain inputs, and you get back a response with certain outputs over the same channel (Http over TCP connection)

Unfortunately, many agents are not good analogs to web servers. They may be **mobile devices** that turn off at 
unpredictable intervals and that lack a stable connection to the network. 
They may need to work **peer-to-peer**, when the internet is not available. 
They may need to interact in time frames of hours or days, not with 30-second timeouts. 
They may not listen over the same channel that they use to talk.

Because of this, the fundamental paradigm for **DIDComm** is 

  - message-based 
  - asynchronous 
  - simplex. 

**Agent X** sends a message over **channel A**. Sometime later, it may receive a response from 
**Agent Y** over **channel B**. 
This is much closer to an email paradigm than a web paradigm

## Motivation

According to The [DIDComm](https://identity.foundation/didcomm-messaging/spec/) design attempts to be:

 - Secure
 - Private
 - Decentralized 
 - Transport-agnostic
 - Routable 
 - Interoperable 
 - Extensible
 - Efficient


This repo contains server-side part of [DIDComm](https://identity.foundation/didcomm-messaging/spec/#message-based-asynchronous-and-simplex) 
infrastructure to solve **DIDComm** issues: 
  
  - routing issues of **mobile devices**: 
  - transport issues
    
issues  of **mobile devices**


#1. Deploy and configuration

#2. Develop and contribute

