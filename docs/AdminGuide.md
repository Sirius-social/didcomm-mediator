# DIDComm mediator admin guide

## Management command

There is management command ```manage``` in container to operate with database records, settings, user account.
Much of these commands duplicate features of Admin Web page

  - Create superuser: enter Admin account username and password via console prompt
    - in container: ```manage create_superuser```
    - out of container: ```docker-compose exec application manage create_superuser```
    
  - Check configs and environment: detect issues, potential drawbacks and errors in environment variables 
    configuration and 
    - in container: ```manage check```
    - out of container: ```docker-compose exec application manage check```

  - Reset user accounts and settings stored in database
    - in container: ```manage reset```
    - out of container: ```docker-compose exec application manage reset```

## WebRoot