# DIDComm mediator admin guide

## Management command

There is management command ```manage``` in container to operate with database records, settings, user account.
Much of these commands duplicate features of Admin Web page

  - Generate seed (to restore mediator did, verkey, secrets)
    - in container: ```manage generate_seed```
    - out of container: ```docker-compose run --rm application manage generate_seed```

  - Create superuser: enter Admin account username and password via console prompt
    - in container: ```manage create_superuser```
    - out of container: ```docker-compose run --rm application manage create_superuser```
    
  - Check configs and environment: detect issues, potential drawbacks and errors in environment variables 
    configuration and 
    - in container: ```manage check```
    - out of container: ```docker-compose run --rm application manage check```

  - Reset user accounts and settings stored in database
    - in container: ```manage reset```
    - out of container: ```docker-compose run --rm application manage reset```
    

## WebRoot

Suppose mediator provide for AgentX endpoint with public URL ```https://mediator-service.com/e/xxx```.
That mean AgentX accessible for outer world by this address and any participant AgentY can
communicate with AgentX in [DIDComm manner](https://identity.foundation/didcomm-messaging/spec/#message-types)

In example above ```https://mediator-service.com``` is Webroot, it is DNS-specific name of server
to make it visible all over internet, it is static part of endpoint addresses with dynamic nature.

**Typing right webroot value is critical part to achieve serviceable endpoints**


**There are two ways to configure webroot:**
  1. Pass environment variable ```WEBROOT``` to docker container
  2. Configure with Admin page

*Notice: environment variable has more priority, so if you have earlier configured webroot via admin page, value provided with env var will replace it*


![Grant endpoint address](_static/rfc0211.svg?raw=true)

See interoperability protocols details:
  - [RFC 0160](https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol): establish P2P connection
  - [RFC 0211](https://github.com/hyperledger/aries-rfcs/tree/master/features/0211-route-coordination): allocate endpoint address by client and maintain routing keys

## Environment variables

### Critical variables:
  - **MEMCACHED**: address of memcached server (caching user sessions and cache database read ops)
  - **MSG_DELIVERY_SERVICES**: comma-separated list of message delivery service addresses, for example ```redis://192.168.1.10,redis://192.168.1.11```
  - **DATABASE_HOST**: address of Postgres server
  - **DATABASE_NAME**: name of Postgres database
  - **DATABASE_USER**: username of Postgres database
  - **DATABASE_PASSWORD**: user password with write privileges to Postgres database
  - **SEED**: secret seed to generate persistent **public key** and **private key** of Mediator App.
    Notice, for the same **seed** you will get **const keys**, so keep this value in secret.

### Optional variables:
  - **WEBROOT**: DNS-specific address of server with Mediator App running.
  - **FCM_API_KEY**, **FCM_SENDER_ID**: Firebase cloud messaging Server **API Keys** to 
    make able route traffic to mobile devices even OS **Power-Save** mode suspend Agent application on device.
  - **CERT_FILE**, **CERT_KEY_FILE**: SSL **certificate** and **cert private key** files  