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

## Installation
Helm chart [https://github.com/Sirius-social/didcomm-helm](https://github.com/Sirius-social/didcomm-helm)

## Motivation

According to The [DIDComm](https://identity.foundation/didcomm-messaging/spec/) design attempts to be:

 - Secure 
 - Private
 - Decentralized 
 - Transport-agnostic
 - Routable *(allows mixed and dynamic transports; passes through mix networks and other generic infrastructure that sees only payload BLOBs)*
 - Interoperable 
 - Extensible
 - Efficient


## Features

This repo contains server-side part of [DIDComm](https://identity.foundation/didcomm-messaging/spec/#message-based-asynchronous-and-simplex) 
infrastructure to solve **DIDComm** challenges in **Mobile Apps development**: 
  
  - **routing** issues of **mobile devices**: 
      - Incoming DID-Communication messages will arrive, even if the mobile agent is behind a firewall 
        and network-address-translation (NAT).
      - Incoming DID-Communication messages continue to arrive, even when the IP address of the mobile agent 
        changes (switching between, 3G, 4G, Wifi, roaming, ...).
  - **transport** issues of **mobile devices**:
      - Thanks to supporting [Firebase cloud messaging](https://firebase.google.com/docs/cloud-messaging)
        DID-Communication messages will arrive independently of Power-Saving mode for specific 
        platform (Android/iOS Power-Doze mode)
      - Each message is transmitted individually in an [Encryption Envelope](https://github.com/hyperledger/aries-rfcs/blob/master/features/0019-encryption-envelope/README.md)
      - Messages are transported via HTTP POST according [DIDComm HTTPS reference](https://identity.foundation/didcomm-messaging/spec/#https)
  - **secure** challenges:
     - Simple encapsulation of DIDcom messages, getting trust from the DIDcom 
       [Encryption Envelope](https://identity.foundation/didcomm-messaging/spec/#summary), so, 
       on top of transport layer, using DIDComm, individuals on semi-connected mobile devices become full peers 
     - In additional server side endpoints use HTTPS with TLS 1.2 (and Websockets ```wss://```) 
       or greater with a forward secret
  - **private** goals:
     - DIDComm uses public key cryptography, not certificates from some parties and passwords from others. 
       Its security guarantees are independent of the transport over which it flows. 
       It is sessionless (though sessions can easily be built atop it). 
       When authentication is required, all parties do it the same way.
     - Registration is self-service, intermediaries require little trust, and no terms and conditions apply.
  - **interoperability**:
     - protocol [Aries-RFC 0160](https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol) 
     to establish P2P connection between **independent Mobile App** and Server-side **Mediator** to 
     authenticate in mediator services (see below)
     - protocol [Aries-RFC 0211](https://github.com/hyperledger/aries-rfcs/tree/master/features/0211-route-coordination)
     to allocate Http endpoint, accessible from internet.
     - protocol [Aries-RFC 0212](https://github.com/Purik/aries-rfcs/tree/main/features/0212-pickup)
     to pull queued messages
     - DIDComm extension [queue transport extension](https://github.com/decentralized-identity/didcomm-messaging/blob/main/extensions/return_route/main.md)
     to indicate duplex channel (via websocket) between edge-agent and mediator. See usage details [here](docs/Mediation.md#using-a-mediator)
  - **efficient**
     - This server app is packed to docker image to rapidly deploy, maintain, [scale with microservices approach](docs/AdminGuide.md#scaling) 
     - Fast to start: appliccation, presented in the repo, has user-friendly admin page and dashboards.

## Mediation Flow

See details here [Mediation.md](docs/Mediation.md)

## Quick Start

You may quickly start with cloud-mediator, check [samples](docs/Developer.md#3-samples) for it

or set-up self-maintained one

  1. Navigate to [docs](docs/) directory and pull all docker images: ```docker-compose pull```
  2. You should generate Mediator public and private keys: ```docker-compose run --rm app manage generate_seed```,
     you will see something like this:
     ```
     =================================================================================
     SEED value is:
                     6tyKXax9gbmyLjRjMXrGouPBQ9SZ8L2h
     place it to SEED environment variable
     =================================================================================
     ```
     **seed** value make it possible to restore Mediator cryptography keys and [DIDs](https://www.w3.org/TR/did-core/)
     independently of hardware and software environment
  2. Replace in [docker-compose.yml](docs/docker-compose.yml) file ```SEED``` environment with generated **seed** on prev step
  3. Run application ```docker-compose up -d``` and open in browser [Admin Page http://localhost:8000/admin](http://localhost:8000/admin) to finish configurations
     via Admin Web Page
     
## Deploy

  - [Admin Guide](docs/AdminGuide.md)
  - [SSL and Proxy](docs/SSL_and_Proxy.md)
  - [Firebase](docs/Firebase.md)
  - [Scaling and Health-Checks](docs/Health_Checks.md)
  - [Helm chart](https://github.com/Sirius-social/didcomm-helm)

## Develop and contribute
  - [Developer Guide](docs/Developer.md)

To contribute code, send message to [support@socialsirius.com](mailto:support@socialsirius.com?subject=Contribute)
or [create issue](https://github.com/Sirius-social/didcomm-mediator/issues/new) 
