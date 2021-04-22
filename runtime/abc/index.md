# ABC

## Docker

### Build

Build the docker image:

```shell
docker build -t abc .
```

### Run

You can **configure** a docker container by configuring a `conf` directory.
Copy the `./conf` template directory as a custom new directory:

```shell
cp -r conf conf_foo # Copy the template configure directory.
```

Configure how your abc-agent introduces itself to the network.
For example change the peer id to `FooBarPeer`, and change opened ports to 8031 and 8032 in `conf_foo/self_contact.json`:

```json
{
  "id" : "FooBarPeer",
  "receiveAddr" : "tcp://127.0.0.1:8031",
  "publishAddr" : "tcp://127.0.0.1:8032"
}
```
Note that this information is sent to  to other peers on the network and it is used by them to connect to your process. If your computer is reachable with the ip address `100.110.120.130` then you need to express that in `conf_foo/self_contact.json`: 


```json
{
  "id" : "FooBarPeer",
  "receiveAddr" : "tcp://100.110.120.130:8031",
  "publishAddr" : "tcp://100.110.120.130:8032"
}
```

Add initial peer contact information in `conf_foo/initial_contacts.json` from the network to connect to at start-up. 
For example, say a node with id `example-com-peer` on addresses `tcp://example.com:8081` and `tcp://example.com:8082` is running. You can add it to the json array in the following way:

```json
[
  {
    "id" : "example-com-peer",
    "receiveAddr" : "tcp://example.com:8081",
    "publishAddr" : "tcp://example.com:8082"
  }
]
```

Your agent generates a private key for usage on start-up. 
Instead, if you own stake or have stake delegated on a specific agent, you can explicitly define your private key in `conf_foo/privkey.json`:

```json
"a2f963a9822a45c4cc59e2a73ce7d4159dafe395d0203c9c745693959ff62c64"
```

Start the docker container. 
Forward the ports that were used in the configuration: `-p 8031:8031 -p 8032:8032`
Mount the configuration directory `-v "$(pwd)"/conf_foo:/app/conf`
The command looks like this:

```shell
docker run -it --rm -p 8031:8031 -p 8032:8032 -v "$(pwd)"/conf_foo:/app/conf aminfa/abc
```

## GUI

To run the web gui you can start a docker composition.
After your changes to the code, build the image:

```shell
docker-compose build
```

And then, run the docker composition and open: http://localhost

```shell
docker-compose up 
```

To shut it down interrupt the process: (ctrl + c)

